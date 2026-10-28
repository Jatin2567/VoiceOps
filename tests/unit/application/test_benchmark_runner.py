"""Regression coverage using real Pipecat lifecycles and local deterministic providers."""
import asyncio
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from pipecat.frames.frames import (
    InputAudioRawFrame, LLMFullResponseEndFrame, OutputAudioRawFrame,
    UserStoppedSpeakingFrame, ErrorFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from backend.application.services.benchmark_runner import BenchmarkRunnerService
from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.domain.models.benchmark import BenchmarkRequest, BenchmarkStatus, PipelineMode
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository
from backend.infrastructure.persistence.supabase_client import SupabaseTelemetryRepository
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher
from backend.pipelines.factory import PipelineFactory, PipelineDAGContext
from backend.pipelines.processors.interceptor import DeterministicSidecarInterceptor
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor


class LocalVoice(FrameProcessor):
    def __init__(self, behavior="respond"):
        super().__init__()
        self.behavior = behavior
        self.audio = bytearray()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, InputAudioRawFrame):
            self.audio.extend(frame.audio)
        await self.push_frame(frame, direction)
        if isinstance(frame, UserStoppedSpeakingFrame):
            if self.behavior == "respond":
                # Delay past the old premature EndFrame deadline.
                await asyncio.sleep(.6)
                await self.push_frame(OutputAudioRawFrame(
                    audio=b"\x00\x00" * 160, sample_rate=16000, num_channels=1))
                await self.push_frame(LLMFullResponseEndFrame())
            elif self.behavior == "error":
                await self.push_error_frame(ErrorFrame(error="Test provider unavailable"))


class LocalFactory:
    def __init__(self, behavior="respond"):
        self.behavior = behavior
        self.voice = None

    def validate_configuration(self, mode):
        pass

    def create_pipeline(self, mode, trace_id):
        self.voice = LocalVoice(self.behavior)
        telemetry = TelemetryProcessor(trace_id, mode, UpstashQueuePublisher())
        interceptor = DeterministicSidecarInterceptor(
            trace_id, GuardrailPolicyService(MockBookingRepository()))
        # Exercise the actual Hybrid interceptor's StartFrame and EndFrame handling.
        pipeline = Pipeline([self.voice, interceptor, telemetry])
        return PipelineDAGContext(mode, trace_id, pipeline, telemetry, interceptor)


class TestBenchmarkRunner(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.audio_path = str(Path(self.temp.name) / "test.wav")
        self.pcm = b"\x01\x00" * 1600
        with wave.open(self.audio_path, "wb") as out:
            out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            out.writeframes(self.pcm)
        self.repo = SupabaseTelemetryRepository()
        self.factory = LocalFactory()
        self.runner = BenchmarkRunnerService(self.factory, self.repo, timeout_secs=2)

    async def asyncTearDown(self):
        await self.runner.stop()
        self.temp.cleanup()

    async def run_benchmark(self):
        req = BenchmarkRequest(mode=PipelineMode.HYBRID, audio_file_path=self.audio_path)
        start = time.perf_counter()
        trace = self.runner.start_benchmark(req)
        self.assertLess(time.perf_counter() - start, .25)
        await asyncio.wait_for(self.runner._active_tasks[trace], 8)
        self.assertFalse(self.runner._active_tasks)
        return await self.repo.get_benchmark_result(trace)

    async def test_hybrid_completes_with_real_lifecycle_and_pcm_frames(self):
        result = await self.run_benchmark()
        self.assertEqual(result.status, BenchmarkStatus.COMPLETED, result.error_message)
        self.assertEqual(bytes(self.factory.voice.audio), self.pcm)
        self.assertGreaterEqual(result.ttfa_ms, 500)
        self.assertIsNone(result.breakdown.stt_latency_ms)
        self.assertIsNone(result.transcription)
        self.assertIsNone(result.response_text)

    async def test_silent_provider_times_out_without_fabricated_metrics(self):
        self.factory.behavior = "silent"
        self.runner.timeout_secs = .2
        result = await self.run_benchmark()
        self.assertEqual(result.status, BenchmarkStatus.FAILED)
        self.assertIn('No complete audio response', result.error_message)
        self.assertIsNone(result.ttfa_ms)

    async def test_provider_error_is_failed_not_completed(self):
        self.factory.behavior = "error"
        result = await self.run_benchmark()
        self.assertEqual(result.status, BenchmarkStatus.FAILED)
        self.assertIn('Test provider unavailable', result.error_message)
        self.assertIsNone(result.ttfa_ms)

    async def test_shutdown_cancels_active_benchmark(self):
        self.factory.behavior = "silent"
        trace = self.runner.start_benchmark(BenchmarkRequest(audio_file_path=self.audio_path))
        await asyncio.sleep(.1)
        await asyncio.wait_for(self.runner.stop(), 5)
        result = await self.repo.get_benchmark_result(trace)
        self.assertEqual(result.status, BenchmarkStatus.FAILED)
        self.assertIn('cancelled', result.error_message)
        self.assertFalse(self.runner._active_tasks)

    async def test_missing_credentials_fail_without_starting_provider(self):
        factory = PipelineFactory(UpstashQueuePublisher(), GuardrailPolicyService(MockBookingRepository()))
        with patch.dict('os.environ', {'GROQ_API_KEY':'', 'GEMINI_API_KEY':''}):
            for mode in PipelineMode:
                with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'API_KEY'):
                    factory.validate_configuration(mode)

    def test_invalid_wav_format_is_rejected(self):
        with wave.open(self.audio_path, 'wb') as out:
            out.setparams((2, 2, 44100, 0, 'NONE', 'not compressed'))
            out.writeframes(self.pcm)
        with self.assertRaisesRegex(ValueError, '16 kHz'):
            self.runner.read_audio(self.audio_path)
