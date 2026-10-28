"""Unit tests for Pipeline Factory and DAG topologies."""
import unittest

from pipecat.pipeline.pipeline import Pipeline

from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.domain.models.benchmark import PipelineMode
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher
from backend.pipelines.factory import PipelineDAGContext, PipelineFactory
from backend.pipelines.modes.cascade_topology import build_cascade_pipeline
from backend.pipelines.modes.hybrid_topology import build_hybrid_pipeline


class TestTopologies(unittest.TestCase):
    """Test suite ensuring both DAG topologies instantiate and link cleanly."""

    def setUp(self):
        self.queue = UpstashQueuePublisher()
        self.repo = MockBookingRepository()
        self.guardrail = GuardrailPolicyService(self.repo)
        self.factory = PipelineFactory(
            queue_publisher=self.queue,
            guardrail_service=self.guardrail,
        )

    def test_build_cascade_topology(self):
        """Verify Cascade DAG creation."""
        pipeline, telemetry = build_cascade_pipeline(
            trace_id="test-cascade",
            queue_publisher=self.queue,
        )
        self.assertIsInstance(pipeline, Pipeline)
        self.assertEqual(telemetry.trace_id, "test-cascade")

    def test_build_hybrid_topology(self):
        """Verify Hybrid S2S with sidecar DAG creation."""
        pipeline, telemetry, interceptor = build_hybrid_pipeline(
            trace_id="test-hybrid",
            queue_publisher=self.queue,
            guardrail_service=self.guardrail,
        )
        self.assertIsInstance(pipeline, Pipeline)
        self.assertIsNotNone(interceptor)

    def test_factory_resolution(self):
        """Verify PipelineFactory resolves both modes."""
        ctx_cascade = self.factory.create_pipeline(PipelineMode.CASCADE, "f-trace-1")
        self.assertEqual(ctx_cascade.mode, PipelineMode.CASCADE)
        self.assertIsNone(ctx_cascade.interceptor)


        ctx_hybrid = self.factory.create_pipeline(PipelineMode.HYBRID, "f-trace-3")
        self.assertEqual(ctx_hybrid.mode, PipelineMode.HYBRID)
        self.assertIsNotNone(ctx_hybrid.interceptor)


if __name__ == "__main__":
    unittest.main()
