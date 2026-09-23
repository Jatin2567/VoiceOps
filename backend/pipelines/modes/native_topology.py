"""Native Topology: Direct Multimodal Speech-to-Speech (Gemini Live API)."""
from typing import Optional, Tuple

from loguru import logger
from pipecat.pipeline.pipeline import Pipeline

from backend.domain.models.benchmark import PipelineMode
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.infrastructure.providers.gemini_live_client import GeminiLiveClient
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor
from backend.pipelines.processors.vad_processor import create_vad_processor


def build_native_pipeline(
    trace_id: str,
    queue_publisher: IQueuePublisher,
    gemini_client: Optional[GeminiLiveClient] = None,
    system_instruction: Optional[str] = None,
) -> Tuple[Pipeline, TelemetryProcessor]:
    """
    Build and link the Native Speech-to-Speech pipeline DAG.
    Architecture:
    Input Audio -> VAD -> Gemini Live LLM (Native S2S, zero guardrail interception) -> TelemetryProcessor -> Sink
    """
    client = gemini_client or GeminiLiveClient()
    vad = create_vad_processor()
    gemini_service = client.create_live_service(
        enable_tools=False,
        custom_system_instruction=system_instruction,
    )
    telemetry = TelemetryProcessor(
        trace_id=trace_id,
        mode=PipelineMode.NATIVE,
        queue_publisher=queue_publisher,
    )

    pipeline = Pipeline([
        vad,
        gemini_service,
        telemetry,
    ])

    logger.info(f"[{trace_id}] Native S2S pipeline DAG built successfully.")
    return pipeline, telemetry
