"""Real Pipecat lifecycle with controlled providers: buffering is observable."""
import asyncio
import io
import wave
from unittest.mock import patch

import pytest
from pipecat.frames.frames import (TranscriptionFrame, LLMFullResponseStartFrame,
    LLMFullResponseEndFrame, LLMTextFrame, TTSStartedFrame, TTSStoppedFrame, TTSAudioRawFrame)
from pipecat.services.groq.llm import GroqLLMService
from backend.application.services.architecture_lab import run_architecture, Observation, sandbox_action
from backend.domain.models.experiment import ExperimentSpec
from backend.infrastructure.providers.recorded_stt import RecordedGroqSTTService
from backend.infrastructure.providers.edge_tts_client import EdgeTTSService


def wav():
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        f.writeframes(b"\x01\x00" * 3200)
    return out.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["buffered", "streaming", "guarded"])
async def test_real_pipeline_progressive_delivery_or_complete_buffer(mode, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    events, completed_at_audio = [], []

    async def stt(service, audio):
        yield TranscriptionFrame("Explain a rainbow.", "user", "")

    async def llm(service, context):
        await service.push_frame(LLMFullResponseStartFrame())
        await service.push_frame(LLMTextFrame("Sunlight enters water. "))
        await asyncio.sleep(.02)
        await service.push_frame(LLMTextFrame("The colors separate."))
        await service.push_frame(LLMFullResponseEndFrame())

    async def tts(service, text, context_id):
        yield TTSStartedFrame(context_id=context_id)
        for _ in range(2):
            await asyncio.sleep(.01)
            yield TTSAudioRawFrame(audio=b"\x01\x00" * 1600, sample_rate=16000,
                                  num_channels=1, context_id=context_id)
        yield TTSStoppedFrame(context_id=context_id)

    def emit(packet):
        events.append(packet)
        if packet["type"] == "audio":
            completed_at_audio.append(any(e.get("name") == "response_complete" for e in events))

    with patch.object(RecordedGroqSTTService, "run_stt", stt), \
         patch.object(GroqLLMService, "_process_context", llm), \
         patch.object(EdgeTTSService, "run_tts", tts):
        result = await run_architecture(ExperimentSpec(), mode, wav(), emit)
    assert result["status"] == "completed", result
    assert result["transcript"] == "Explain a rainbow."
    assert result["response"] == "Sunlight enters water. The colors separate."
    assert result["metrics"]["stt_ms"] is not None
    assert result["metrics"]["server_complete_ms"] >= result["metrics"]["server_first_audio_ms"]
    assert completed_at_audio
    assert all(completed_at_audio) if mode == "buffered" else not completed_at_audio[0]


@pytest.mark.asyncio
async def test_sandbox_policy_changes_outcome_without_external_effects():
    spec = ExperimentSpec(task="action", action_limit=100)
    o = Observation(lambda event: None)
    args = {"action": "refund", "amount": 150}
    base = await sandbox_action(spec, "streaming", args, o)
    guarded = await sandbox_action(spec, "guarded", args, o)
    allowed = await sandbox_action(spec, "guarded", {"action": "refund", "amount": 50}, o)
    unknown = await sandbox_action(spec, "guarded", {"action": "delete", "amount": 0}, o)
    assert base["status"] == allowed["status"] == "simulated"
    assert guarded["status"] == unknown["status"] == "blocked"
    assert all(t["external_effect"] is False for t in o.tools)
    assert len(o.tools) == 4


def test_schedule_rotates_and_configuration_is_bounded():
    from pydantic import ValidationError
    spec = ExperimentSpec(repeats=3)
    schedule = spec.schedule()
    assert schedule[0] == (1, "buffered")
    assert schedule[3] == (2, "streaming")
    assert schedule[6] == (3, "guarded")
    with pytest.raises(ValidationError):
        ExperimentSpec(modes=["streaming", "streaming"])
    with pytest.raises(ValidationError):
        ExperimentSpec(repeats=4)
    with pytest.raises(ValidationError):
        ExperimentSpec(action_limit=float("nan"))
