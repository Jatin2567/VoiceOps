"""Cascade Topology: STT (Groq Whisper) -> LLM (Groq LLM) -> TTS (EdgeTTSService)."""
import os
from typing import Optional, Tuple

from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames.frames import TranscriptionFrame, LLMContextFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService

from backend.domain.models.benchmark import PipelineMode
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.infrastructure.providers.edge_tts_client import EdgeTTSService
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor
from pipecat.processors.aggregators.llm_response_universal import LLMAssistantAggregator
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from backend.pipelines.booking_tools import BOOKING_TOOLS


class TranscriptToContext(FrameProcessor):
    """Single-utterance benchmarks send the recognized text to the LLM explicitly."""
    def __init__(self, context, **kwargs):
        super().__init__(**kwargs)
        self.context = context

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            self.context.add_message({"role": "user", "content": frame.text})
            await self.push_frame(LLMContextFrame(self.context), direction)


def build_cascade_pipeline(
    trace_id: str,
    queue_publisher: IQueuePublisher,
    groq_api_key: Optional[str] = None,
    edge_voice: Optional[str] = None,
    whisper_model: str = "whisper-large-v3-turbo",
    llm_model: str = "openai/gpt-oss-20b",
    interceptor=None,
    system_instruction: Optional[str] = None,
    conversation_context=None,
) -> Tuple[Pipeline, TelemetryProcessor]:
    """
    Build and link the Cascade pipeline DAG.
    Architecture:
    Input Audio -> VAD -> Groq Whisper STT -> Groq LLM LLM -> Edge-TTS -> TelemetryProcessor -> Sink
    """
    api_key = groq_api_key or (os.getenv("GROQ_API_KEY") or "gsk_placeholder_key")

    stt = GroqSTTService(api_key=api_key, settings=GroqSTTService.Settings(model=os.getenv("GROQ_WHISPER_MODEL") or whisper_model))
    llm = GroqLLMService(api_key=api_key, settings=GroqLLMService.Settings(model=os.getenv("GROQ_LLM_MODEL") or llm_model))
    instruction = "You are VoiceOps, a helpful voice assistant. Reply in one short sentence. Do not claim to book appointments."
    tools = None
    if interceptor:
        instruction = (
            "You are VoiceOps clinic assistant. Use the provided tools for every booking, "
            "cancellation and availability request. Never confirm success before the tool returns success. "
            "Respect blocked results and explain the policy briefly. Ask for missing details. "
            "Do not speak a preliminary confirmation before calling tools. Reply concisely."
        )
        tools = ToolsSchema(standard_tools=[FunctionSchema(
            name=t["name"], description=t["description"],
            properties=t["parameters"]["properties"], required=t["parameters"]["required"]
        ) for t in BOOKING_TOOLS])
        for tool in BOOKING_TOOLS:
            llm.register_function(tool["name"], interceptor.handle_tool_call)
    context = conversation_context or LLMContext(messages=[{"role": "system", "content": instruction + " " + (system_instruction or "")}])
    if tools:
        context.set_tools(tools)
    tts = EdgeTTSService(voice=edge_voice)
    telemetry = TelemetryProcessor(
        trace_id=trace_id,
        mode=PipelineMode.HYBRID if interceptor else PipelineMode.CASCADE,
        queue_publisher=queue_publisher,
    )
    telemetry.conversation_context = context

    pipeline = Pipeline([
        stt,
        TranscriptToContext(context),
        llm,
        tts,
        *([interceptor] if interceptor else []),
        telemetry,
        LLMAssistantAggregator(context),
    ])

    logger.info(f"[{trace_id}] Cascade pipeline DAG built successfully.")
    return pipeline, telemetry
