"""Run bounded voice benchmarks and persist only observed results."""
import asyncio
import time
import wave
from contextlib import suppress
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

from loguru import logger
from pipecat.frames.frames import (InputAudioRawFrame, UserStoppedSpeakingFrame,
    UserStartedSpeakingFrame, VADUserStartedSpeakingFrame, VADUserStoppedSpeakingFrame)
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

from backend.domain.models.benchmark import (
    BenchmarkRequest, BenchmarkResult, BenchmarkStatus, LatencyBreakdown, PipelineMode,
)
from backend.domain.ports.telemetry_repository import ITelemetryRepository
from backend.pipelines.factory import PipelineFactory


class BenchmarkRunnerService:
    PCM_CHUNK_SIZE = 3200

    def __init__(self, pipeline_factory: PipelineFactory,
                 telemetry_repository: ITelemetryRepository, timeout_secs: float = 30.0):
        self.factory = pipeline_factory
        self.telemetry_repo = telemetry_repository
        self.timeout_secs = timeout_secs
        self._active_tasks: Dict[str, asyncio.Task] = {}

    def start_benchmark(self, request: BenchmarkRequest) -> str:
        trace_id = request.trace_id or str(uuid4())
        request.trace_id = trace_id
        self._active_tasks[trace_id] = asyncio.create_task(
            self._run_pipeline_background(request, trace_id), name=f"benchmark_{trace_id}"
        )
        return trace_id

    async def get_benchmark_result(self, trace_id: str) -> Optional[BenchmarkResult]:
        return await self.telemetry_repo.get_benchmark_result(trace_id)

    async def stop(self) -> None:
        """Cancel active benchmarks before the application closes its telemetry store."""
        tasks = list(self._active_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def read_audio(path: Optional[str]) -> bytes:
        """Decode the WAV container; providers expect raw 16-bit mono PCM, not headers."""
        if not path:
            raise ValueError("A 16 kHz mono PCM WAV file is required.")
        with wave.open(path, "rb") as source:
            if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
                raise ValueError("Audio must be a 16 kHz, mono, 16-bit PCM WAV file.")
            audio = source.readframes(source.getnframes())
        if not audio:
            raise ValueError("The WAV file contains no audio.")
        return audio

    async def _run_pipeline_background(self, request: BenchmarkRequest, trace_id: str) -> None:
        started = time.perf_counter()
        runner = None
        run_future = None
        response_future = None
        feed_future = None
        result = BenchmarkResult(trace_id=trace_id, mode=request.mode,
                                 status=BenchmarkStatus.RUNNING)
        try:
            await self.telemetry_repo.save_benchmark_result(result)
            self.factory.validate_configuration(request.mode)
            audio = self.read_audio(request.audio_file_path)
            context = self.factory.create_pipeline(mode=request.mode, trace_id=trace_id)
            task = PipelineTask(context.pipeline, enable_rtvi=False,
                                cancel_timeout_secs=2.0, setup_timeout_secs=5.0,
                                start_timeout_secs=5.0)
            # The web server owns process signals, not individual benchmark runs.
            runner = PipelineRunner(handle_sigint=False, handle_sigterm=False)
            errors = []

            @task.event_handler("on_pipeline_error")
            async def on_error(_task, frame):
                errors.append(frame.error)
                await runner.cancel()

            started_event = asyncio.Event()

            @task.event_handler("on_pipeline_started")
            async def on_started(_task, _frame):
                started_event.set()

            async def feed_audio():
                await started_event.wait()
                await task.queue_frame(VADUserStartedSpeakingFrame())
                await task.queue_frame(UserStartedSpeakingFrame())
                for offset in range(0, len(audio), self.PCM_CHUNK_SIZE):
                    chunk = audio[offset:offset + self.PCM_CHUNK_SIZE]
                    await task.queue_frame(InputAudioRawFrame(
                        audio=chunk, sample_rate=16000, num_channels=1))
                    # Pace file audio like microphone input; priority turn markers
                    # must not overtake the queued PCM frames.
                    await asyncio.sleep(len(chunk) / 32000)
                await task.queue_frame(VADUserStoppedSpeakingFrame())
                await task.queue_frame(UserStoppedSpeakingFrame())

            await runner.add_workers(task)
            run_future = asyncio.create_task(runner.run())
            feed_future = asyncio.create_task(feed_audio())
            response_future = asyncio.create_task(context.telemetry_processor.response_finished.wait())
            done, _ = await asyncio.wait(
                [run_future, response_future], timeout=self.timeout_secs,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                raise TimeoutError(f"No complete audio response within {self.timeout_secs:g} seconds.")
            if errors:
                raise RuntimeError(errors[0])
            if response_future in done:
                # End only after the response has crossed the pipeline, never after a fixed 0.5s.
                await task.stop_when_done()
                finished, _ = await asyncio.wait([run_future], timeout=3.0)
                if not finished:
                    raise TimeoutError("Pipeline did not shut down after its response.")
            await run_future
            ttfa = context.telemetry_processor.computed_ttfa_ms
            if ttfa is None or not context.telemetry_processor.response_finished.is_set():
                raise RuntimeError("Pipeline ended without a complete audio response.")
            result.status = BenchmarkStatus.COMPLETED
            result.ttfa_ms = ttfa
            result.transcription = context.telemetry_processor.transcription
            result.response_text = context.telemetry_processor.response_text or None
            result.breakdown = LatencyBreakdown(
                total_turn_latency_ms=round((time.perf_counter() - started) * 1000, 2))
            if context.interceptor:
                result.interception_count = context.interceptor.interception_count
                result.guardrail_violations = context.interceptor.violations_detected
                result.breakdown.guardrail_overhead_ms = context.interceptor.total_overhead_ms
        except asyncio.CancelledError:
            result.status = BenchmarkStatus.FAILED
            result.error_message = "Benchmark cancelled during shutdown."
            raise
        except Exception as exc:
            result.status = BenchmarkStatus.FAILED
            result.error_message = str(exc)
            logger.warning(f"[{trace_id}] Benchmark failed: {exc}")
        finally:
            if feed_future:
                feed_future.cancel()
                with suppress(asyncio.CancelledError):
                    await feed_future
            if response_future:
                response_future.cancel()
                with suppress(asyncio.CancelledError):
                    await response_future
            if run_future and not run_future.done():
                await runner.cancel()
                done, _ = await asyncio.wait([run_future], timeout=3.0)
                if not done:
                    run_future.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await run_future
            result.completed_at = datetime.now(timezone.utc)
            await self.telemetry_repo.save_benchmark_result(result)
            self._active_tasks.pop(trace_id, None)
