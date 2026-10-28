"""Unit tests for Supabase telemetry repository adapter."""
import unittest
from datetime import datetime, timezone

from backend.domain.models.benchmark import BenchmarkResult, BenchmarkStatus, PipelineMode
from backend.domain.models.telemetry import TelemetryEvent, TelemetryEventType, TTFAMetric
from backend.domain.ports.telemetry_repository import ITelemetryRepository
from backend.infrastructure.persistence.supabase_client import SupabaseTelemetryRepository


class TestSupabaseTelemetryRepository(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring SupabaseTelemetryRepository fulfills ITelemetryRepository."""

    async def asyncSetUp(self):
        # Initialized without credentials to test robust in-memory fallback behavior
        self.repo: ITelemetryRepository = SupabaseTelemetryRepository(
            supabase_url=None, supabase_key=None
        )

    def test_implements_interface(self):
        """Verify contract implementation."""
        self.assertIsInstance(self.repo, ITelemetryRepository)

    async def test_save_and_retrieve_benchmark_result(self):
        """Verify benchmark result persistence and lookup."""
        result = BenchmarkResult(
            trace_id="trace-supabase-01",
            mode=PipelineMode.CASCADE,
            status=BenchmarkStatus.COMPLETED,
            ttfa_ms=420.5,
            transcription="Hello world",
            response_text="Hello! How can I help?",
            completed_at=datetime.now(timezone.utc),
        )
        await self.repo.save_benchmark_result(result)

        retrieved = await self.repo.get_benchmark_result("trace-supabase-01")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.trace_id, "trace-supabase-01")
        self.assertEqual(retrieved.ttfa_ms, 420.5)
        self.assertEqual(retrieved.mode, PipelineMode.CASCADE)

    async def test_save_metric_and_batch(self):
        """Verify TTFA metric and batch persistence."""
        m1 = TTFAMetric(
            trace_id="trace-m1",
            mode=PipelineMode.CASCADE,
            t0_timestamp_ms=1000.0,
            t1_timestamp_ms=1350.0,
        )
        m2 = TTFAMetric(
            trace_id="trace-m2",
            mode=PipelineMode.HYBRID,
            t0_timestamp_ms=2000.0,
            t1_timestamp_ms=2480.0,
        )
        await self.repo.save_metric(m1)
        await self.repo.save_metrics_batch([m2])

    async def test_save_event_and_list_recent(self):
        """Verify telemetry event saving and recent benchmark listing."""
        event = TelemetryEvent(
            trace_id="trace-m1",
            event_type=TelemetryEventType.USER_STOPPED_SPEAKING,
            timestamp_ms=1000.0,
        )
        await self.repo.save_event(event)

        recent = await self.repo.list_recent_benchmarks(limit=10)
        self.assertIsInstance(recent, list)


if __name__ == "__main__":
    unittest.main()
