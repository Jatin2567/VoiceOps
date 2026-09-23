"""Cascade Topology: STT (Groq Whisper) -> LLM (Groq Llama-3) -> TTS (EdgeTTSService)."""
import os
from typing import Optional, Tuple

from loguru import logger
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService

from backend.domain.models.benchmark import PipelineMode
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.infrastructure.providers.edge_tts_client import EdgeTTSService
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor
from backend.pipelines.processors.vad_processor import create_vad_processor


def build_cascade_pipeline(
    trace_id: str,
    queue_publisher: IQueuePublisher,
    groq_api_key: Optional[str] = None,
    edge_voice: Optional[str] = None,
    whisper_model: str = "whisper-large-v3-turbo",
    llama_model: str = "llama-3.3-70b-versatile",
) -> Tuple[Pipeline, TelemetryProcessor]:
    """
    Build and link the Cascade pipeline DAG.
    Architecture:
    Input Audio -> VAD -> Groq Whisper STT -> Groq Llama-3 LLM -> Edge-TTS -> TelemetryProcessor -> Sink
    """
    api_key = groq_api_key or os.getenv("GROQ_API_KEY", "gsk_placeholder_key")

    vad = create_vad_processor()
    stt = GroqSTTService(api_key=api_key, settings=GroqSTTService.Settings(model=whisper_model))
    llm = GroqLLMService(api_key=api_key, settings=GroqLLMService.Settings(model=llama_model))
    tts = EdgeTTSService(voice=edge_voice)
    telemetry = TelemetryProcessor(
        trace_id=trace_id,
        mode=PipelineMode.CASCADE,
        queue_publisher=queue_publisher,
    )

    pipeline = Pipeline([
        vad,
        stt,
        llm,
        tts,
        telemetry,
    ])

    logger.info(f"[{trace_id}] Cascade pipeline DAG built successfully.")
    return pipeline, telemetry
