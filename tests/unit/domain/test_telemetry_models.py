"""Unit tests for Telemetry and TTFA domain models."""
import unittest
from uuid import UUID

from backend.domain.models.benchmark import PipelineMode
from backend.domain.models.telemetry import (
    TelemetryBatch,
    TelemetryEvent,
    TelemetryEventType,
    TTFAMetric,
)


class TestTelemetryModels(unittest.TestCase):
    """Test suite for telemetry models and TTFA calculation."""

    def test_ttfa_auto_calculation(self):
        """Verify TTFA is automatically calculated as T1 - T0."""
        t0 = 1711200000100.0  # T0: UserStoppedSpeakingFrame
        t1 = 1711200000550.5  # T1: AudioOutputFrame
        metric = TTFAMetric(
            trace_id="ttfa-trace-1",
            mode=PipelineMode.CASCADE,
            t0_timestamp_ms=t0,
            t1_timestamp_ms=t1,
        )
        self.assertAlmostEqual(metric.ttfa_ms, 450.5, places=2)

    def test_ttfa_negative_or_inverted_clamping(self):
        """Verify inverted timestamps clamp TTFA to 0.0."""
        t0 = 1000.0
        t1 = 900.0
        metric = TTFAMetric(
            trace_id="ttfa-trace-2",
            mode=PipelineMode.CASCADE,
            t0_timestamp_ms=t0,
            t1_timestamp_ms=t1,
        )
        self.assertEqual(metric.ttfa_ms, 0.0)

    def test_telemetry_event_generation(self):
        """Verify TelemetryEvent fields and UUID creation."""
        event = TelemetryEvent(
            trace_id="trace-evt-1",
            event_type=TelemetryEventType.USER_STOPPED_SPEAKING,
            timestamp_ms=1711200000000.0,
            payload={"vad_confidence": 0.98}
        )
        self.assertIsNotNone(event.event_id)
        UUID(event.event_id)
        self.assertEqual(event.event_type, TelemetryEventType.USER_STOPPED_SPEAKING)
        self.assertEqual(event.payload["vad_confidence"], 0.98)

    def test_telemetry_batch_aggregation(self):
        """Verify TelemetryBatch collects metrics and events."""
        m1 = TTFAMetric(
            trace_id="trace-1",
            mode=PipelineMode.CASCADE,
            t0_timestamp_ms=100.0,
            t1_timestamp_ms=450.0,
        )
        e1 = TelemetryEvent(
            trace_id="trace-1",
            event_type=TelemetryEventType.LLM_FIRST_TOKEN,
            timestamp_ms=250.0,
        )
        batch = TelemetryBatch(metrics=[m1], events=[e1])
        self.assertEqual(len(batch.metrics), 1)
        self.assertEqual(len(batch.events), 1)
        self.assertEqual(batch.metrics[0].ttfa_ms, 350.0)
        self.assertIsNotNone(batch.batch_id)


if __name__ == "__main__":
    unittest.main()
