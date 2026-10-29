"""Unit tests for custom Edge-TTS Pipecat adapter (Directive 3)."""
import unittest
import os

from pipecat.frames.frames import AudioRawFrame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
from pipecat.services.tts_service import TTSService

from backend.infrastructure.providers.edge_tts_client import EdgeTTSService


class TestEdgeTTSClient(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring EdgeTTSService inherits TTSService and yields AudioRawFrames."""

    def setUp(self):
        self.service = EdgeTTSService(voice="en-US-ChristopherNeural", sample_rate=16000)

    def test_inherits_pipecat_tts_service(self):
        """CRITICAL: Verify EdgeTTSService explicitly inherits from Pipecat base TTSService."""
        self.assertTrue(issubclass(EdgeTTSService, TTSService))
        self.assertIsInstance(self.service, TTSService)

    async def test_empty_text_handling(self):
        """Verify handling empty or whitespace text yields start and stop frames."""
        frames = [f async for f in self.service.run_tts("", context_id="ctx-empty")]
        self.assertEqual(len(frames), 2)
        self.assertIsInstance(frames[0], TTSStartedFrame)
        self.assertIsInstance(frames[1], TTSStoppedFrame)

    @unittest.skipUnless(os.getenv("RUN_LIVE_PROVIDER_TESTS") == "1", "Opt-in Edge-TTS network test")
    async def test_run_tts_yields_audio_raw_frames(self):
        """
        CRITICAL (Directive 3): Verify run_tts executes synthesis and yields AudioRawFrame objects.
        """
        frames = []
        async for frame in self.service.run_tts("Testing VoiceOps audio", context_id="ctx-01"):
            frames.append(frame)

        self.assertGreater(len(frames), 2, "Expected start, audio frames, and stop frame")
        self.assertIsInstance(frames[0], TTSStartedFrame)
        self.assertIsInstance(frames[-1], TTSStoppedFrame)

        # Check audio frames
        audio_frames = [f for f in frames if isinstance(f, AudioRawFrame)]
        self.assertGreater(len(audio_frames), 0, "Must yield at least one AudioRawFrame")

        for af in audio_frames:
            self.assertIsInstance(af, AudioRawFrame)
            self.assertEqual(af.sample_rate, 16000)
            self.assertEqual(af.num_channels, 1)
            self.assertGreater(len(af.audio), 0)


if __name__ == "__main__":
    unittest.main()
