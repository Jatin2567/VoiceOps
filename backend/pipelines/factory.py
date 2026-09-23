"""Pipeline factory resolving PipelineMode to the initialized topology DAG."""
from dataclasses import dataclass
from typing import Optional

from loguru import logger
from pipecat.pipeline.pipeline import Pipeline

from backend.domain.models.benchmark import PipelineMode
from backend.domain.ports.guardrail_policy import IGuardrailPolicyService
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.infrastructure.providers.gemini_live_client import GeminiLiveClient
from backend.pipelines.modes.cascade_topology import build_cascade_pipeline
from backend.pipelines.modes.hybrid_topology import build_hybrid_pipeline
from backend.pipelines.modes.native_topology import build_native_pipeline
from backend.pipelines.processors.interceptor import DeterministicSidecarInterceptor
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor


@dataclass
class PipelineDAGContext:
    """Encapsulates the assembled Pipecat Pipeline and its telemetry/interception probes."""
    mode: PipelineMode
    trace_id: str
    pipeline: Pipeline
    telemetry_processor: TelemetryProcessor
    interceptor: Optional[DeterministicSidecarInterceptor] = None


class PipelineFactory:
    """
    Factory creating fully configured Pipecat DAG pipelines corresponding to the target PipelineMode.
    """

    def __init__(
        self,
        queue_publisher: IQueuePublisher,
        guardrail_service: IGuardrailPolicyService,
        gemini_client: Optional[GeminiLiveClient] = None,
    ):
        self.queue_publisher = queue_publisher
        self.guardrail_service = guardrail_service
        self.gemini_client = gemini_client or GeminiLiveClient()

    def create_pipeline(
        self,
        mode: PipelineMode,
        trace_id: str,
        system_instruction: Optional[str] = None,
    ) -> PipelineDAGContext:
        """
        Instantiate and link the requested pipeline topology.
        """
        logger.info(f"Resolving pipeline topology for mode={mode.value}, trace_id={trace_id}")

        if mode == PipelineMode.CASCADE:
            pipeline, telemetry = build_cascade_pipeline(
                trace_id=trace_id,
                queue_publisher=self.queue_publisher,
            )
            return PipelineDAGContext(
                mode=mode,
                trace_id=trace_id,
                pipeline=pipeline,
                telemetry_processor=telemetry,
                interceptor=None,
            )

        elif mode == PipelineMode.NATIVE:
            pipeline, telemetry = build_native_pipeline(
                trace_id=trace_id,
                queue_publisher=self.queue_publisher,
                gemini_client=self.gemini_client,
                system_instruction=system_instruction,
            )
            return PipelineDAGContext(
                mode=mode,
                trace_id=trace_id,
                pipeline=pipeline,
                telemetry_processor=telemetry,
                interceptor=None,
            )

        elif mode == PipelineMode.HYBRID:
            pipeline, telemetry, interceptor = build_hybrid_pipeline(
                trace_id=trace_id,
                queue_publisher=self.queue_publisher,
                guardrail_service=self.guardrail_service,
                gemini_client=self.gemini_client,
                system_instruction=system_instruction,
            )
            return PipelineDAGContext(
                mode=mode,
                trace_id=trace_id,
                pipeline=pipeline,
                telemetry_processor=telemetry,
                interceptor=interceptor,
            )

        else:
            raise ValueError(f"Unsupported pipeline mode: {mode}")
