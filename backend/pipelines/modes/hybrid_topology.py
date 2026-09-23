"""Hybrid Topology: Gemini Live Multimodal S2S with Deterministic Sidecar Interception."""
from typing import Optional, Tuple

from loguru import logger
from pipecat.pipeline.pipeline import Pipeline

from backend.domain.models.benchmark import PipelineMode
from backend.domain.ports.guardrail_policy import IGuardrailPolicyService
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.infrastructure.providers.gemini_live_client import GeminiLiveClient
from backend.pipelines.processors.interceptor import DeterministicSidecarInterceptor
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor
from backend.pipelines.processors.vad_processor import create_vad_processor


def build_hybrid_pipeline(
    trace_id: str,
    queue_publisher: IQueuePublisher,
    guardrail_service: IGuardrailPolicyService,
    gemini_client: Optional[GeminiLiveClient] = None,
    system_instruction: Optional[str] = None,
) -> Tuple[Pipeline, TelemetryProcessor, DeterministicSidecarInterceptor]:
    """
    Build and link the Hybrid pipeline DAG.
    Architecture:
    Input Audio -> VAD -> Gemini Live LLM (with tool schemas) -> DeterministicSidecarInterceptor -> TelemetryProcessor -> Sink
    """
    client = gemini_client or GeminiLiveClient()
    vad = create_vad_processor()
    gemini_service = client.create_live_service(
        enable_tools=True,
        custom_system_instruction=system_instruction,
    )
    interceptor = DeterministicSidecarInterceptor(
        trace_id=trace_id,
        guardrail_service=guardrail_service,
    )
    telemetry = TelemetryProcessor(
        trace_id=trace_id,
        mode=PipelineMode.HYBRID,
        queue_publisher=queue_publisher,
    )

    pipeline = Pipeline([
        vad,
        gemini_service,
        interceptor,
        telemetry,
    ])

    logger.info(f"[{trace_id}] Hybrid pipeline DAG built successfully with sidecar guardrail interceptor.")
    return pipeline, telemetry, interceptor
