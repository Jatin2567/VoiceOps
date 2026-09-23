"""Unit tests for Gemini Live client adapter."""
import unittest

from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService

from backend.infrastructure.providers.gemini_live_client import GeminiLiveClient


class TestGeminiLiveClient(unittest.TestCase):
    """Test suite for Google Gemini Multimodal Live API provider adapter."""

    def setUp(self):
        self.client = GeminiLiveClient(api_key=None)

    def test_default_configuration(self):
        """Verify model and voice defaults."""
        self.assertEqual(self.client.model, "gemini-2.0-flash-exp")
        self.assertEqual(self.client.voice_id, "Aoede")
        self.assertFalse(self.client.is_configured)

    def test_tool_declarations_present(self):
        """Verify tool schemas for hybrid sidecar are defined."""
        tool_names = [t["name"] for t in self.client.BOOKING_TOOLS_DECLARATION]
        self.assertIn("check_slot_availability", tool_names)
        self.assertIn("schedule_appointment", tool_names)
        self.assertIn("cancel_appointment", tool_names)

    def test_create_live_service_instance(self):
        """Verify factory creates a valid GeminiLiveLLMService instance."""
        service = self.client.create_live_service(enable_tools=True)
        self.assertIsInstance(service, GeminiLiveLLMService)
        self.assertEqual(service._settings.model, self.client.model)
        self.assertEqual(service._settings.voice, self.client.voice_id)


if __name__ == "__main__":
    unittest.main()
