"""Google Gemini Multimodal Live API provider adapter for Native and Hybrid speech-to-speech."""
import os
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService, GeminiLiveLLMSettings


class GeminiLiveClient:
    """
    Client adapter configuring and initializing Google Gemini Multimodal Live API
    for end-to-end Speech-to-Speech (S2S) in Native and Hybrid topologies.
    """

    DEFAULT_MODEL = "gemini-2.0-flash-exp"
    DEFAULT_VOICE = "Aoede"

    BOOKING_TOOLS_DECLARATION = [
        {
            "name": "check_slot_availability",
            "description": "Check if a given date and time appointment slot is available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "slot_time": {
                        "type": "string",
                        "description": "ISO 8601 formatted date-time string (e.g. 2026-09-25T14:00:00Z)"
                    },
                    "service_type": {
                        "type": "string",
                        "description": "Service name: consultation, cleaning, checkup",
                        "enum": ["consultation", "cleaning", "checkup", "procedure", "follow_up"]
                    }
                },
                "required": ["slot_time", "service_type"]
            }
        },
        {
            "name": "schedule_appointment",
            "description": "Schedule a new confirmed appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Full name of customer"},
                    "customer_phone": {"type": "string", "description": "Customer contact telephone number"},
                    "slot_time": {"type": "string", "description": "ISO 8601 UTC slot date time"},
                    "service_type": {"type": "string", "description": "Type of service requested"},
                    "notes": {"type": "string", "description": "Optional notes or complaints"}
                },
                "required": ["customer_name", "customer_phone", "slot_time", "service_type"]
            }
        },
        {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string", "description": "Booking ID to cancel"},
                    "reason": {"type": "string", "description": "Reason for cancellation"}
                },
                "required": ["booking_id"]
            }
        }
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice_id: Optional[str] = None,
        system_instruction: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_LIVE_MODEL", self.DEFAULT_MODEL)
        self.voice_id = voice_id or self.DEFAULT_VOICE
        self.system_instruction = (
            system_instruction
            or (
                "You are an executive dental & medical voice assistant for VoiceOps Clinic. "
                "Be polite, concise, and professional. Always verify availability before confirming bookings."
            )
        )

        if not self.api_key or self.api_key.startswith("AIzaSy_your_"):
            logger.info("No active GEMINI_API_KEY detected. Gemini Live client in mock/simulation mode.")
        else:
            logger.info(f"Gemini Live client configured with model={self.model}, voice={self.voice_id}.")

    @property
    def is_configured(self) -> bool:
        """Return True if real API key is present."""
        return bool(self.api_key and not self.api_key.startswith("AIzaSy_your_"))

    def create_live_service(
        self,
        enable_tools: bool = False,
        custom_tools: Optional[List[Any]] = None,
        custom_system_instruction: Optional[str] = None,
    ) -> GeminiLiveLLMService:
        """
        Factory creating an initialized Pipecat GeminiLiveLLMService instance
        ready for insertion into the Pipecat Audio DAG.
        """
        tools_list = None
        if enable_tools:
            tools_list = custom_tools if custom_tools is not None else self.BOOKING_TOOLS_DECLARATION

        # Use valid placeholder if running offline tests
        active_key = self.api_key if self.is_configured else "mock_gemini_api_key"

        service = GeminiLiveLLMService(
            api_key=active_key,
            settings=GeminiLiveLLMService.Settings(
                model=self.model,
                voice=self.voice_id,
            ),
            system_instruction=custom_system_instruction or self.system_instruction,
            tools=tools_list,
        )
        return service
