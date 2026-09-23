"""Unit tests for Upstash Redis queue adapter."""
import unittest

from backend.domain.models.benchmark import PipelineMode
from backend.domain.models.telemetry import TelemetryEvent, TelemetryEventType, TTFAMetric
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher


class TestUpstashQueuePublisher(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring UpstashQueuePublisher fulfills IQueuePublisher contract."""

    async def asyncSetUp(self):
        # Uses in-memory fallback for local deterministic testing
        self.queue: IQueuePublisher = UpstashQueuePublisher(url=None, token=None, redis_url=None)

    def test_implements_interface(self):
        """Verify contract implementation."""
        self.assertIsInstance(self.queue, IQueuePublisher)

    async def test_push_and_pop_metrics_fifo(self):
        """Verify FIFO outbox behavior with LPUSH and RPOP."""
        m1 = TTFAMetric(
            trace_id="q-trace-1",
            mode=PipelineMode.CASCADE,
            t0_timestamp_ms=100.0,
            t1_timestamp_ms=450.0,
        )
        m2 = TTFAMetric(
            trace_id="q-trace-2",
            mode=PipelineMode.HYBRID,
            t0_timestamp_ms=200.0,
            t1_timestamp_ms=620.0,
        )

        await self.queue.push_metric(m1)
        await self.queue.push_metric(m2)

        depth = await self.queue.get_queue_depth()
        self.assertEqual(depth, 2)

        popped = await self.queue.pop_metrics(batch_size=10)
        self.assertEqual(len(popped), 2)
        # FIFO: m1 was pushed first, so RPOP yields m1 first
        self.assertEqual(popped[0].trace_id, "q-trace-1")
        self.assertEqual(popped[1].trace_id, "q-trace-2")

        empty_depth = await self.queue.get_queue_depth()
        self.assertEqual(empty_depth, 0)

    async def test_push_and_pop_events(self):
        """Verify pushing and popping granular pipeline telemetry events."""
        event = TelemetryEvent(
            trace_id="q-trace-event",
            event_type=TelemetryEventType.USER_STARTED_SPEAKING,
            timestamp_ms=500.0,
            payload={"source": "mic"}
        )
        await self.queue.push_event(event)

        popped = await self.queue.pop_events(batch_size=5)
        self.assertEqual(len(popped), 1)
        self.assertEqual(popped[0].trace_id, "q-trace-event")
        self.assertEqual(popped[0].event_type, TelemetryEventType.USER_STARTED_SPEAKING)


if __name__ == "__main__":
    unittest.main()
