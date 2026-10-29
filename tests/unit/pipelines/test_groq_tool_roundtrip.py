"""Exercise the real Groq callback machinery with deterministic provider outputs."""
import wave
from unittest.mock import patch

import pytest
from pipecat.frames.frames import (
    FunctionCallFromLLM, LLMFullResponseStartFrame, LLMFullResponseEndFrame,
    LLMTextFrame, TranscriptionFrame, UserStoppedSpeakingFrame, TTSAudioRawFrame,
    TTSStartedFrame, TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.groq.llm import GroqLLMService

from backend.application.services.benchmark_runner import BenchmarkRunnerService
from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.domain.models.benchmark import BenchmarkRequest, PipelineMode
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository
from backend.infrastructure.persistence.supabase_client import SupabaseTelemetryRepository
from backend.infrastructure.providers.edge_tts_client import EdgeTTSService
from backend.infrastructure.providers.recorded_stt import RecordedGroqSTTService
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher
from backend.pipelines.factory import PipelineFactory


class RecordedSTT(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if isinstance(frame, UserStoppedSpeakingFrame):
            await self.push_frame(TranscriptionFrame("Cancel my appointment.", "user", ""))


@pytest.mark.asyncio
@pytest.mark.parametrize("booking_id, expected", [("book-001", "success"), ("missing", "error")])
@pytest.mark.parametrize("batch", [False, True])
async def test_groq_guardrail_result_resumes_spoken_reply(tmp_path, monkeypatch, booking_id, expected, batch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    contexts = []

    async def completion(llm, context):
        contexts.append(list(context.messages))
        await llm.push_frame(LLMFullResponseStartFrame())
        if len(contexts) == 1:
            await llm.run_function_calls([FunctionCallFromLLM(
                function_name="cancel_appointment", tool_call_id="call-1",
                arguments={"booking_id": booking_id}, context=context,
            )])
        else:
            await llm.push_frame(LLMTextFrame("Your request has been checked."))
        await llm.push_frame(LLMFullResponseEndFrame())

    async def speech(tts, text, context_id):
        yield TTSStartedFrame(context_id=context_id)
        yield TTSAudioRawFrame(audio=b"\x01\x00" * 1600, sample_rate=16000,
                               num_channels=1, context_id=context_id)
        yield TTSStoppedFrame(context_id=context_id)

    path = tmp_path / "voice.wav"
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        out.writeframes(b"\x01\x00" * 1600)
    bookings = MockBookingRepository(seed_sample_data=True)
    repo = SupabaseTelemetryRepository()
    factory = PipelineFactory(UpstashQueuePublisher(), GuardrailPolicyService(bookings))
    runner = BenchmarkRunnerService(factory, repo, timeout_secs=5)
    request = BenchmarkRequest(mode=PipelineMode.HYBRID, audio_file_path=str(path), metadata={"recorded_utterance": batch})
    async def recorded_speech(stt, audio):
        assert audio[:4] == b"RIFF"
        yield TranscriptionFrame("Cancel my appointment.", "user", "")
    # Preserve the STT Settings type used while constructing the topology.
    from pipecat.services.groq.stt import GroqSTTService
    RecordedSTT.Settings = GroqSTTService.Settings
    try:
        with patch("backend.pipelines.modes.cascade_topology.GroqSTTService", RecordedGroqSTTService if batch else RecordedSTT), \
             patch.object(RecordedGroqSTTService, "run_stt", recorded_speech), \
             patch.object(GroqLLMService, "_process_context", completion), \
             patch.object(EdgeTTSService, "run_tts", speech):
            await runner._run_pipeline_background(request, request.trace_id)
        result = await repo.get_benchmark_result(request.trace_id)
        assert result.status.value == "completed", result.error_message
        assert result.interception_count == 1
        assert len(contexts) == 2
        tool_result = next(m for m in contexts[-1] if m.get("role") == "tool")
        import json
        assert json.loads(tool_result["content"])["status"] == expected
        assert bool(result.guardrail_violations) == (expected == "error")
        assert result.ttfa_ms is not None
        assert result.response_text
    finally:
        await runner.stop()
