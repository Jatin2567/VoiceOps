"""Call boundary tests: malformed audio, isolation, capacity and retry identity."""
import io
import time
import wave
from uuid import uuid4
import pytest
from backend.application.services.voice_calls import VoiceCalls, CallError


def audio():
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        f.writeframes(b"\x01\x00" * 1600)
    return out.getvalue()


@pytest.fixture
def calls(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    from backend.application.services.usage_budget import UsageBudget
    monkeypatch.setattr("backend.application.services.voice_calls.usage_budget", UsageBudget(str(tmp_path / "calls.sqlite")))
    return VoiceCalls()


def test_isolation_expiry_and_end(calls):
    first, second = calls.create(), calls.create()
    assert calls.get(first).bookings is not calls.get(second).bookings
    calls.get(first).touched = time.monotonic() - 1801
    with pytest.raises(CallError, match="") as exc:
        calls.get(first)
    assert exc.value.status == 404
    calls.end(second)
    assert not calls.sessions


@pytest.mark.asyncio
async def test_bad_audio_and_busy_call(calls):
    key = calls.create()
    with pytest.raises(CallError) as exc:
        await calls.turn(key, str(uuid4()), b"not wav")
    assert exc.value.status == 422
    async with calls.get(key).lock:
        with pytest.raises(CallError) as exc:
            await calls.turn(key, str(uuid4()), audio())
        assert exc.value.status == 409
    assert calls.active_turns == 0


@pytest.mark.asyncio
async def test_duplicate_turn_returns_original_without_execution(calls):
    import hashlib
    key, tid = calls.create(), str(uuid4())
    wav = audio()
    result = {"trace_id": "original"}
    calls.get(key).cache[tid] = (hashlib.sha256(wav).hexdigest(), result)
    assert await calls.turn(key, tid, wav) is result
    with pytest.raises(CallError) as exc:
        await calls.turn(key, tid, wav + b"changed")
    assert exc.value.status == 409


def test_audio_limit_and_configuration(calls, monkeypatch):
    with pytest.raises(CallError) as exc:
        calls.validate_audio(b"a" * 960045)
    assert exc.value.status == 413
    monkeypatch.setenv("GROQ_API_KEY", "")
    with pytest.raises(ValueError):
        calls.create()


def test_session_capacity(calls):
    calls.MAX_SESSIONS = 1
    calls.create()
    with pytest.raises(CallError) as exc:
        calls.create()
    assert exc.value.status == 503
