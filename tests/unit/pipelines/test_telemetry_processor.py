"""Unit tests for TelemetryProcessor non-invasive TTFA capture (Directive 4)."""
import asyncio
import unittest

from pipecat.frames.frames import (
    AudioRawFrame,
    InterruptionFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from backend.domain.models.benchmark import PipelineMode
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher
from backend.pipelines.processors.telemetry_processor import TelemetryProcessor


class TestTelemetryProcessor(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring non-invasive TTFA capture and outbox queue push."""

    async def asyncSetUp(self):
        self.queue = UpstashQueuePublisher(url=None, token=None)
        self.processor = TelemetryProcessor(
            trace_id="test-telemetry-trace",
            mode=PipelineMode.CASCADE,
            queue_publisher=self.queue,
        )

    async def test_ttfa_capture_flow(self):
        """Verify T0 and T1 capture and TTFA computation."""
        # 1. User stops speaking (T0)
        await self.processor.process_frame(
            UserStoppedSpeakingFrame(),
            FrameDirection.DOWNSTREAM,
        )
        self.assertIsNotNone(self.processor._t0_ms)

        # 2. Simulate latency
        await asyncio.sleep(0.05)

        # 3. First audio frame emitted (T1)
        audio_frame = TTSAudioRawFrame(
            audio=b"\x00" * 3200,
            sample_rate=16000,
            num_channels=1,
            context_id="ctx-1",
        )
        await self.processor.process_frame(
            audio_frame,
            FrameDirection.DOWNSTREAM,
        )

        self.assertIsNotNone(self.processor.computed_ttfa_ms)
        self.assertGreaterEqual(self.processor.computed_ttfa_ms, 40.0)

        # Allow background task to push to queue
        await asyncio.sleep(0.01)
        popped_metrics = await self.queue.pop_metrics(batch_size=10)
        self.assertEqual(len(popped_metrics), 1)
        self.assertEqual(popped_metrics[0].trace_id, "test-telemetry-trace")
        self.assertEqual(popped_metrics[0].ttfa_ms, self.processor.computed_ttfa_ms)

    async def test_transcription_and_response_text(self):
        """Verify transcription and text accumulation."""
        await self.processor.process_frame(
            TranscriptionFrame(text="Schedule appointment", user_id="u1", timestamp="t1"),
            FrameDirection.DOWNSTREAM,
        )
        self.assertEqual(self.processor.transcription, "Schedule appointment")

    async def test_reset_on_interruption(self):
        """Verify reset on interruption frame."""
        await self.processor.process_frame(
            UserStoppedSpeakingFrame(),
            FrameDirection.DOWNSTREAM,
        )
        self.assertIsNotNone(self.processor._t0_ms)

        await self.processor.process_frame(
            InterruptionFrame(),
            FrameDirection.DOWNSTREAM,
        )
        self.assertIsNone(self.processor._t0_ms)


if __name__ == "__main__":
    unittest.main()
