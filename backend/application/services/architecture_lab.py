"""Pipecat experiments with observed stage events and progressive PCM delivery.

All modes share providers, input and tools. Buffered mode holds LLM text before
TTS and holds output audio until completion. Streaming modes deliver PCM as it
crosses the output probe. Guarded mode additionally enforces sandbox policy.
"""
import asyncio
import base64
import hashlib
import json
import os
import time
from contextlib import suppress
from uuid import uuid4
import platform
import importlib.metadata
from loguru import logger

from pipecat.frames.frames import (LLMTextFrame, LLMFullResponseEndFrame,
    TTSAudioRawFrame, TranscriptionFrame, UserStoppedSpeakingFrame)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMAssistantAggregator
from pipecat.services.groq.llm import GroqLLMService
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema

from backend.infrastructure.providers.recorded_stt import RecordedGroqSTTService, RecordedUtteranceFrame
from backend.infrastructure.providers.edge_tts_client import EdgeTTSService
from backend.pipelines.modes.cascade_topology import TranscriptToContext
from backend.application.services.voice_calls import VoiceCalls
from backend.application.services.experiment_evaluation import evaluate


class Observation:
    def __init__(self, emit):
        self.started = time.perf_counter()
        self.emit = emit
        self.events = []
        self.first = {}
        self.transcript = ""
        self.text = []
        self.audio = bytearray()
        self.done = asyncio.Event()
        self.tools = []

    def mark(self, name, **details):
        ms = round((time.perf_counter() - self.started) * 1000, 2)
        self.first.setdefault(name, ms)
        event = {"name": name, "ms": ms, **details}
        self.events.append(event)
        self.emit({"type": "stage", **event})


class TextGate(FrameProcessor):
    def __init__(self, observation, buffered, action_expected=False):
        super().__init__()
        self.o, self.buffered, self.parts = observation, buffered, []
        self.confirmed = False
        self.action_expected = action_expected

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMTextFrame):
            if "llm_first_token" not in self.o.first:
                self.o.mark("llm_first_token")
            if self.action_expected and not self.o.tools:
                return
            if self.o.tools:
                # Only verified tool outcomes may describe an action. The model's
                # post-tool prose never reaches speech synthesis or the report.
                if self.confirmed:
                    return
                self.confirmed = True
                frame = LLMTextFrame(" ".join(action_confirmation(t) for t in self.o.tools))
                self.o.mark("verified_confirmation")
            self.o.text.append(frame.text)
            if self.buffered:
                self.parts.append(frame.text)
                return
        if isinstance(frame, LLMFullResponseEndFrame):
            self.o.mark("llm_response_end")
            if self.parts:
                await self.push_frame(LLMTextFrame("".join(self.parts)), direction)
                self.parts.clear()
        await self.push_frame(frame, direction)


class STTProbe(FrameProcessor):
    def __init__(self, observation):
        super().__init__()
        self.o = observation

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            self.o.transcript = frame.text
            self.o.mark("transcript_ready")
            self.o.emit({"type": "transcript", "text": frame.text})
        await self.push_frame(frame, direction)


class LabSpeech(EdgeTTSService):
    def __init__(self, observation):
        super().__init__()
        self.o = observation

    async def run_tts(self, text, context_id):
        self.o.mark("tts_request")
        async for frame in super().run_tts(text, context_id):
            yield frame


class OutputProbe(FrameProcessor):
    def __init__(self, observation, buffered):
        super().__init__()
        self.o, self.buffered = observation, buffered

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TTSAudioRawFrame):
            if "first_audio_generated" not in self.o.first:
                self.o.mark("first_audio_generated")
            self.o.audio.extend(frame.audio)
            if not self.buffered:
                self.o.emit({"type": "audio", "pcm": base64.b64encode(frame.audio).decode()})
        if isinstance(frame, LLMFullResponseEndFrame) and self.o.audio:
            self.o.mark("response_complete")
            self.o.done.set()
        await self.push_frame(frame, direction)


def action_confirmation(result):
    action = result["action"]
    if result["status"] == "blocked":
        return f"The {action} request was blocked by the sandbox policy. No real action occurred."
    return f"Simulation only: the {action} request for {result['amount']:g} units passed the sandbox checks. No real booking, payment, cancellation or delivery was made."


async def sandbox_action(spec, mode, arguments, observation):
    """Pure simulation: no external actions, money, scheduling or network effects."""
    start = time.perf_counter()
    action = str(arguments.get("action", ""))[:80]
    amount = arguments.get("amount")
    # Baseline transport validation applies to every mode.
    valid = isinstance(amount, (int, float)) and not isinstance(amount, bool) and 0 <= amount <= 10000
    blocked = not valid or (mode == "guarded" and
                           (action not in spec.allowed_actions or amount > spec.action_limit))
    result = {"status": "blocked" if blocked else "simulated", "action": action,
              "amount": amount, "external_effect": False}
    if blocked:
        result["reason"] = "Action must be allowed and its amount must be within the configured policy limit."
    record = {**result, "policy_enforced": mode == "guarded",
              "overhead_ms": round((time.perf_counter() - start) * 1000, 3)}
    observation.tools.append(record)
    observation.mark("tool_result", **record)
    return result


async def run_architecture(spec, mode, audio, emit, history=None):
    VoiceCalls.validate_audio(audio)
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("Groq is not configured on the server.")
    o = Observation(emit)
    trace = str(uuid4())
    instruction = ("You are VoiceOps, a general-purpose voice assistant. Reply with plain speech. "
                   "Follow the requested task. Use only tools explicitly provided in this request. "
                   "If no tools are provided, respond in text and do not attempt any tool calls. "
                   "Never claim a real external action occurred. ")
    tasks = {"conversation": "Answer the user's question.",
             "knowledge": "Answer only from the reference context; say when it lacks the answer.",
             "extraction": "Extract the requested fields concisely; do not invent missing values.",
             "action": "Use sandbox_action to simulate the requested action and report its result."}
    # Same policy description is visible in all modes; only guarded executes deterministic checks.
    instruction += f"{tasks[spec.task]} {spec.instruction}\nReference context:\n{spec.context}"
    if spec.task == "action":
        instruction += f"\nSandbox policy: allowed actions {spec.allowed_actions}; amount limit {spec.action_limit}."
        instruction += " Always submit the requested action and amount to sandbox_action, including requests exceeding policy; let the tool decide. Do not speak before the tool returns."
    if spec.task == "conversation":
        instruction += (f"\nAn optional sandbox_action tool is available for requested action simulations. "
                        f"Allowed actions: {spec.allowed_actions}; amount limit {spec.action_limit}. "
                        "Ordinary questions need no tool. For action requests use only sandbox_action; "
                        "report its outcome as a simulation and never claim a purchase or booking occurred. "
                        "Wait for the tool result before describing an action outcome.")
    if spec.task == "extraction":
        instruction += " Return only a valid JSON object containing the fields requested in the reference material."
    context = LLMContext(messages=[{"role": "system", "content": instruction}, *(history or [])[-12:]])
    stt = RecordedGroqSTTService(api_key=key, settings=RecordedGroqSTTService.Settings(
        model=os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")))
    llm = GroqLLMService(api_key=key, settings=GroqLLMService.Settings(
        model=os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-20b"), temperature=0, max_completion_tokens=1024))
    if spec.task in ("action", "conversation"):
        context.set_tools(ToolsSchema(standard_tools=[FunctionSchema(name="sandbox_action",
            description="Simulate an action; never changes any external system.",
            properties={"action": {"type": "string"}, "amount": {"type": "number"}},
            required=["action", "amount"])]))

        async def tool(params):
            result = await sandbox_action(spec, mode, params.arguments, o)
            await params.result_callback(result)
        llm.register_function("sandbox_action", tool)
    buffer_text = mode in ("buffered", "text_buffered")
    buffer_audio = mode in ("buffered", "audio_buffered")
    pipeline = Pipeline([stt, STTProbe(o), TranscriptToContext(context), llm,
        TextGate(o, buffer_text, action_expected=spec.task == "action"), LabSpeech(o), OutputProbe(o, buffer_audio), LLMAssistantAggregator(context)])
    task = PipelineTask(pipeline, enable_rtvi=False, cancel_timeout_secs=2,
                        setup_timeout_secs=5, start_timeout_secs=5)
    runner = PipelineRunner(handle_sigint=False, handle_sigterm=False)
    errors, futures = [], []

    @task.event_handler("on_pipeline_started")
    async def started(_task, _frame):
        o.mark("stt_request")
        await task.queue_frame(UserStoppedSpeakingFrame())
        await task.queue_frame(RecordedUtteranceFrame(audio=audio))

    @task.event_handler("on_pipeline_error")
    async def failed(_task, frame):
        errors.append("Voice provider or pipeline failed; inspect server logs using the trace ID.")
        o.done.set()

    status, error = "completed", None
    try:
        await runner.add_workers(task)
        running = asyncio.create_task(runner.run())
        waiting = asyncio.create_task(o.done.wait())
        futures = [running, waiting]
        done, _ = await asyncio.wait(futures, timeout=60, return_when=asyncio.FIRST_COMPLETED)
        if not done or errors or not o.audio or "response_complete" not in o.first:
            raise RuntimeError(errors[0] if errors else "No complete response within the 60-second deadline.")
        await task.stop_when_done()
        await asyncio.wait_for(asyncio.shield(running), 4)
        if buffer_audio:
            # Same 100 ms PCM packet size; only release time differs.
            for offset in range(0, len(o.audio), 3200):
                emit({"type": "audio", "pcm": base64.b64encode(o.audio[offset:offset+3200]).decode()})
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        status, error = "failed", str(exc)
        logger.warning(f"Lab trace {trace} ({mode}) failed: {type(exc).__name__}")
    finally:
        if futures and not futures[0].done():
            with suppress(Exception):
                await asyncio.wait_for(runner.cancel(), 4)
        for future in futures:
            if not future.done():
                future.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await future
    answer = "".join(o.text)
    versions = {name: importlib.metadata.version(name) for name in ("pipecat-ai", "groq", "edge-tts")}
    def delta(end, start):
        return round(o.first[end] - o.first[start], 2) if end in o.first and start in o.first else None
    return {"trace_id": trace, "mode": mode, "status": status, "error": error,
        "transcript": o.transcript, "response": answer, "events": o.events,
        "metrics": {"stt_ms": delta("transcript_ready", "stt_request"),
            "llm_first_token_ms": delta("llm_first_token", "transcript_ready"),
            "tts_first_audio_ms": delta("first_audio_generated", "tts_request"),
            "server_first_audio_ms": o.first.get("first_audio_generated"),
            "server_complete_ms": o.first.get("response_complete"),
            "tool_overhead_ms": round(sum(t["overhead_ms"] for t in o.tools), 3)},
        "tools": o.tools, "audio_sha256": hashlib.sha256(audio).hexdigest(),
        "evaluation": evaluate(spec, answer, o.tools),
        "configuration": {"buffer_text": buffer_text, "buffer_audio": buffer_audio, "policy_enforced": mode == "guarded",
                          "action_confirmation": "verified tool outcome template"},
        "runtime": {"commit": os.getenv("RENDER_GIT_COMMIT", os.getenv("VOICEOPS_COMMIT", "local-unversioned")),
                    "python": platform.python_version(), "dependencies": versions, "region": os.getenv("RENDER_REGION", "unknown")},
        "phrase_match": spec.expected_phrase.casefold() in answer.casefold() if spec.expected_phrase else None,
        "providers": {"stt": os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
                      "llm": os.getenv("GROQ_LLM_MODEL", "openai/gpt-oss-20b"), "tts": "Edge-TTS",
                      "voice": os.getenv("EDGE_TTS_VOICE", EdgeTTSService.DEFAULT_VOICE), "sample_rate": 16000,
                      "llm_settings": {"temperature": 0, "max_completion_tokens": 1024}}}
