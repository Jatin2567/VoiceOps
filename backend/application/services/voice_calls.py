"""Bounded, isolated microphone conversations using the benchmark Pipecat engine."""
import asyncio
import base64
import hashlib
import io
import tempfile
import time
import wave
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.application.services.benchmark_runner import BenchmarkRunnerService
from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.domain.models.benchmark import BenchmarkRequest, PipelineMode
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository
from backend.pipelines.factory import PipelineFactory, PipelineDAGContext
from backend.pipelines.modes.cascade_topology import build_cascade_pipeline
from backend.pipelines.processors.interceptor import DeterministicSidecarInterceptor
from backend.application.services.usage_budget import usage_budget, BudgetExceeded


class LocalTelemetry:
    """Call audio and transcripts never enter the shared benchmark history."""
    def __init__(self):
        self.result = None

    async def save_benchmark_result(self, result):
        self.result = result

    async def push_event(self, event):
        pass

    async def push_metric(self, metric):
        pass


class CallFactory(PipelineFactory):
    def __init__(self, bookings):
        super().__init__(LocalTelemetry(), GuardrailPolicyService(bookings))
        self.context = None
        self.latest = None

    def create_pipeline(self, mode, trace_id, system_instruction=None):
        interceptor = DeterministicSidecarInterceptor(
            trace_id, self.guardrail_service, callback_driven=True)
        pipeline, telemetry = build_cascade_pipeline(
            trace_id, self.queue_publisher, interceptor=interceptor,
            conversation_context=self.context,
            system_instruction=(
                f"Today is {datetime.now(timezone.utc).isoformat()}. "
                "This is an isolated demo clinic. All appointment times are UTC. "
                "Use IDs from prior tool results when the caller says cancel that appointment. "
                "Never invent names, phone numbers, dates or IDs. "
                "Respond with plain speech, no markdown, emoji, or long IDs unless requested. "
                "Keep the response to at most two short sentences."
            ),
        )
        telemetry.capture_audio = True
        self.context = telemetry.conversation_context
        self.latest = PipelineDAGContext(mode, trace_id, pipeline, telemetry, interceptor)
        return self.latest


@dataclass
class CallSession:
    bookings: MockBookingRepository = field(default_factory=lambda: MockBookingRepository(False))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    touched: float = field(default_factory=time.monotonic)
    cache: dict = field(default_factory=dict)
    turns: int = 0
    factory: CallFactory = field(init=False)

    def __post_init__(self):
        self.factory = CallFactory(self.bookings)


class CallError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class VoiceCalls:
    MAX_AUDIO_BYTES = 960044
    MAX_SESSIONS = 24
    TTL = 1800

    def __init__(self):
        self.sessions = {}
        self.active_turns = 0

    def create(self):
        now = time.monotonic()
        self.sessions = {k: v for k, v in self.sessions.items()
                         if v.lock.locked() or now - v.touched < self.TTL}
        if len(self.sessions) >= self.MAX_SESSIONS:
            raise CallError(503, "All call rooms are busy. Try again shortly.")
        session = CallSession()
        session.factory.validate_configuration(PipelineMode.HYBRID)
        key = str(uuid4())
        self.sessions[key] = session
        return key

    def get(self, key):
        session = self.sessions.get(key)
        if not session or (not session.lock.locked() and time.monotonic() - session.touched > self.TTL):
            self.sessions.pop(key, None)
            raise CallError(404, "Call expired. Start a new call.")
        return session

    def end(self, key):
        session = self.get(key)
        if session.lock.locked():
            raise CallError(409, "Wait for the current reply before ending the call.")
        del self.sessions[key]

    @staticmethod
    def validate_audio(audio):
        if len(audio) > VoiceCalls.MAX_AUDIO_BYTES:
            raise CallError(413, "Keep each recording under 30 seconds.")
        try:
            with wave.open(io.BytesIO(audio), "rb") as source:
                if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
                    raise ValueError()
                frames = source.getnframes()
                pcm = source.readframes(frames)
                if not 1600 <= frames <= 480000 or len(pcm) != frames * 2:
                    raise ValueError()
        except (wave.Error, EOFError, ValueError):
            raise CallError(422, "Use a 0.1–30 second, 16 kHz mono PCM WAV recording.")

    async def turn(self, key, turn_id, audio):
        session = self.get(key)
        digest = hashlib.sha256(audio).hexdigest()
        if turn_id in session.cache:
            prior_digest, response = session.cache[turn_id]
            if prior_digest != digest:
                raise CallError(409, "This turn ID belongs to a different recording.")
            return response
        self.validate_audio(audio)
        if session.lock.locked():
            raise CallError(409, "A reply is already in progress for this call.")
        if self.active_turns >= 2:
            raise CallError(503, "Voice capacity is busy. Try again shortly.")
        if session.turns >= 12:
            raise CallError(409, "This call reached 12 turns. Start a new call.")
        try:
            usage_budget.reserve("call-studio", 1)
        except BudgetExceeded as exc:
            raise CallError(429, str(exc))
        async with session.lock:
            self.active_turns += 1
            session.turns += 1
            session.touched = time.monotonic()
            trace = str(uuid4())
            store = LocalTelemetry()
            runner = BenchmarkRunnerService(session.factory, store, timeout_secs=60)
            path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
                    file.write(audio)
                    path = Path(file.name)
                request = BenchmarkRequest(trace_id=trace, mode=PipelineMode.HYBRID,
                                           audio_file_path=str(path), session_id=key,
                                           metadata={"recorded_utterance": True})
                await runner._run_pipeline_background(request, trace)
                result = store.result
                response = result.model_dump(mode="json")
                response["turn_id"] = turn_id
                response["audio_base64"] = None
                if result.status.value == "completed":
                    output = io.BytesIO()
                    with wave.open(output, "wb") as wav:
                        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                        wav.writeframes(session.factory.latest.telemetry_processor.output_audio)
                    response["audio_base64"] = base64.b64encode(output.getvalue()).decode()
                else:
                    response["error_message"] = (
                        "The voice provider could not finish this turn. Check the booking list before "
                        "trying again: a tool may already have completed. Reference: " + trace)
                response["bookings"] = [b.model_dump(mode="json") for b in await session.bookings.list_bookings()]
                session.cache[turn_id] = (digest, response)
                # Keep only the most recent audio response; IDs remain cached to prevent re-execution.
                for cached_id, (_, cached) in session.cache.items():
                    if cached_id != turn_id:
                        cached["audio_base64"] = None
                return response
            finally:
                await runner.stop()
                if path:
                    path.unlink(missing_ok=True)
                session.touched = time.monotonic()
                self.active_turns -= 1


voice_calls = VoiceCalls()
