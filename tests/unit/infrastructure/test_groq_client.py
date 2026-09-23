"""Unit tests for Groq provider client adapter."""
import unittest

from backend.infrastructure.providers.groq_client import GroqClient


class TestGroqClient(unittest.IsolatedAsyncioTestCase):
    """Test suite for Groq Whisper and Llama-3 API client."""

    async def asyncSetUp(self):
        self.client = GroqClient(api_key=None)

    def test_initialization(self):
        """Verify client initializes in mock mode when key is absent."""
        self.assertFalse(self.client.is_connected)

    async def test_transcribe_audio(self):
        """Verify audio transcription produces text and latency metrics."""
        dummy_audio = b"\x00\x00" * 16000  # 1 second of mock PCM silence
        res = await self.client.transcribe_audio(dummy_audio)
        self.assertIn("text", res)
        self.assertIn("latency_ms", res)
        self.assertGreater(len(res["text"]), 0)

    async def test_generate_chat_completion(self):
        """Verify chat completion generation."""
        messages = [{"role": "user", "content": "Schedule a checkup"}]
        res = await self.client.generate_chat_completion(messages)
        self.assertIn("content", res)
        self.assertIn("latency_ms", res)

    async def test_stream_chat(self):
        """Verify token streaming generator yields text tokens."""
        messages = [{"role": "user", "content": "Hello"}]
        tokens = [token async for token in self.client.stream_chat(messages)]
        self.assertGreater(len(tokens), 0)
        full_text = "".join(tokens)
        self.assertIn("schedule", full_text.lower())


if __name__ == "__main__":
    unittest.main()
