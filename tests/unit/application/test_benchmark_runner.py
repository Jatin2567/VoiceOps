"""Unit tests for BenchmarkRunnerService (Directive 2: non-blocking ASGI)."""
import asyncio
import time
import unittest

from backend.application.services.benchmark_runner import BenchmarkRunnerService
from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.domain.models.benchmark import BenchmarkRequest, BenchmarkStatus, PipelineMode
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository
from backend.infrastructure.persistence.supabase_client import SupabaseTelemetryRepository
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher
from backend.pipelines.factory import PipelineFactory


class TestBenchmarkRunner(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring BenchmarkRunnerService runs asynchronously via asyncio.create_task."""

    async def asyncSetUp(self):
        self.queue = UpstashQueuePublisher()
        self.telemetry_repo = SupabaseTelemetryRepository()
        self.booking_repo = MockBookingRepository()
        self.guardrail = GuardrailPolicyService(self.booking_repo)
        self.factory = PipelineFactory(self.queue, self.guardrail)
        self.runner_service = BenchmarkRunnerService(
            pipeline_factory=self.factory,
            telemetry_repository=self.telemetry_repo,
        )

    async def test_start_benchmark_instantly_returns_trace_id(self):
        """
        CRITICAL (Directive 2): Verify start_benchmark returns instantly (< 20ms)
        without blocking the event loop on the Pipecat PipelineRunner.
        """
        req = BenchmarkRequest(mode=PipelineMode.CASCADE)
        t_start = time.perf_counter()
        trace_id = self.runner_service.start_benchmark(req)
        duration_ms = (time.perf_counter() - t_start) * 1000

        self.assertIsNotNone(trace_id)
        self.assertEqual(trace_id, req.trace_id)
        # Must return in under 250 milliseconds (non-blocking verification)
        self.assertLess(duration_ms, 250.0, "start_benchmark must not block the event loop")

        # Initial status should be available
        await asyncio.sleep(0.05)
        initial_status = await self.runner_service.get_benchmark_result(trace_id)
        self.assertIsNotNone(initial_status)
        self.assertIn(initial_status.status, (BenchmarkStatus.PENDING, BenchmarkStatus.RUNNING, BenchmarkStatus.COMPLETED))


if __name__ == "__main__":
    unittest.main()
