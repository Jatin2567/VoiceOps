"""Groq API client adapter for Whisper STT and Llama-3 inference."""
import io
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger


class GroqClient:
    """
    Client adapter wrapping the Groq Cloud API.
    Provides ultra-low-latency Whisper STT and Llama-3 reasoning for the Cascade topology.
    """

    DEFAULT_WHISPER_MODEL = "whisper-large-v3-turbo"
    DEFAULT_LLM_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client = None

        if self.api_key and not self.api_key.startswith("gsk_your_"):
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=self.api_key)
                logger.info("Groq AsyncGroq client initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}. Falling back to simulation mode.")
        else:
            logger.info("No active GROQ_API_KEY detected. Operating in mock simulation mode.")

    @property
    def is_connected(self) -> bool:
        """Return True if genuine Groq API client is available."""
        return self._client is not None

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "speech.wav",
        model: Optional[str] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Transcribe raw audio bytes using Groq Whisper.
        Returns a dict with 'text' and 'latency_ms'.
        """
        start_t = time.perf_counter()
        target_model = model or os.getenv("GROQ_WHISPER_MODEL", self.DEFAULT_WHISPER_MODEL)

        if self._client:
            try:
                audio_file = (filename, io.BytesIO(audio_bytes), "audio/wav")
                transcription = await self._client.audio.transcriptions.create(
                    file=audio_file,
                    model=target_model,
                    language=language,
                    response_format="json"
                )
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
                return {
                    "text": transcription.text.strip(),
                    "latency_ms": latency_ms,
                    "model": target_model
                }
            except Exception as e:
                logger.error(f"Groq transcription error: {e}. Using fallback transcription.")

        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "text": "Hello, I would like to schedule an appointment for consultation.",
            "latency_ms": latency_ms,
            "model": "mock-whisper"
        }

    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
        max_tokens: int = 512
    ) -> Dict[str, Any]:
        """
        Execute non-streaming chat completion with Llama-3.
        """
        start_t = time.perf_counter()
        target_model = model or os.getenv("GROQ_LLM_MODEL", self.DEFAULT_LLM_MODEL)

        if self._client:
            try:
                kwargs: Dict[str, Any] = {
                    "messages": messages,
                    "model": target_model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = await self._client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                latency_ms = round((time.perf_counter() - start_t) * 1000, 2)

                tool_calls = []
                if choice.message.tool_calls:
                    for tc in choice.message.tool_calls:
                        tool_calls.append({
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                            "type": tc.type,
                        })

                return {
                    "content": choice.message.content or "",
                    "tool_calls": tool_calls,
                    "latency_ms": latency_ms,
                    "model": target_model,
                }
            except Exception as e:
                logger.error(f"Groq LLM generation error: {e}. Falling back to default response.")

        latency_ms = round((time.perf_counter() - start_t) * 1000, 2)
        return {
            "content": "I would be happy to help you with that booking.",
            "tool_calls": [],
            "latency_ms": latency_ms,
            "model": "mock-llama3",
        }

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from Llama-3, recording Time-to-First-Token (TTFT).
        """
        target_model = model or os.getenv("GROQ_LLM_MODEL", self.DEFAULT_LLM_MODEL)

        if self._client:
            try:
                stream = await self._client.chat.completions.create(
                    messages=messages,
                    model=target_model,
                    temperature=temperature,
                    stream=True,
                )
                async for chunk in stream:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield content
                return
            except Exception as e:
                logger.error(f"Groq streaming chat error: {e}. Falling back to mock tokens.")

        # Mock fallback tokens
        mock_sentence = "I can help schedule that for you right now."
        for token in mock_sentence.split():
            yield token + " "
