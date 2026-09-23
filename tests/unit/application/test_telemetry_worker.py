"""Unit tests for TelemetryFlushWorker (Directive 4: Decoupled Outbox)."""
import asyncio
import unittest

from backend.application.telemetry.worker import TelemetryFlushWorker
from backend.domain.models.benchmark import PipelineMode
from backend.domain.models.telemetry import TelemetryEvent, TelemetryEventType, TTFAMetric
from backend.infrastructure.persistence.supabase_client import SupabaseTelemetryRepository
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher


class TestTelemetryWorker(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring TelemetryFlushWorker decouples DB I/O from real-time audio."""

    async def asyncSetUp(self):
        self.queue = UpstashQueuePublisher()
        self.repo = SupabaseTelemetryRepository()
        self.worker = TelemetryFlushWorker(
            queue_publisher=self.queue,
            telemetry_repository=self.repo,
            batch_size=10,
            poll_interval_secs=0.05,
        )

    async def test_flush_once_transfers_queue_to_persistence(self):
        """Verify flush_once pops metrics from queue and writes to repository."""
        metric = TTFAMetric(
            trace_id="worker-test-m1",
            mode=PipelineMode.HYBRID,
            t0_timestamp_ms=100.0,
            t1_timestamp_ms=450.0,
        )
        event = TelemetryEvent(
            trace_id="worker-test-m1",
            event_type=TelemetryEventType.USER_STOPPED_SPEAKING,
            timestamp_ms=100.0,
        )

        await self.queue.push_metric(metric)
        await self.queue.push_event(event)

        initial_depth = await self.queue.get_queue_depth()
        self.assertEqual(initial_depth, 2)

        flushed = await self.worker.flush_once()
        self.assertEqual(flushed, 2)

        final_depth = await self.queue.get_queue_depth()
        self.assertEqual(final_depth, 0)

        # Check repository received metric
        self.assertIn("worker-test-m1", self.repo._in_memory_metrics)

    async def test_worker_lifecycle_start_stop(self):
        """Verify worker starts and stops gracefully."""
        self.assertFalse(self.worker.is_running)
        await self.worker.start()
        self.assertTrue(self.worker.is_running)

        await asyncio.sleep(0.1)

        await self.worker.stop()
        self.assertFalse(self.worker.is_running)


if __name__ == "__main__":
    unittest.main()
