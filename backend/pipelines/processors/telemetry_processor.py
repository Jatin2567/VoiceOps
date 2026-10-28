"""Pipecat FrameProcessor for non-invasive TTFA capture and telemetry outbox push."""
import asyncio
import time
from typing import List, Optional

from loguru import logger
from pipecat.frames.frames import (
    AudioRawFrame,
    Frame,
    InterruptionFrame,
    LLMTextFrame,
    LLMFullResponseEndFrame,
    OutputAudioRawFrame,
    TextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSTextFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from backend.domain.models.benchmark import PipelineMode
from backend.domain.models.telemetry import TelemetryEvent, TelemetryEventType, TTFAMetric
from backend.domain.ports.queue_publisher import IQueuePublisher


class TelemetryProcessor(FrameProcessor):
    """
    Non-invasive FrameProcessor observing frame events flowing through the Pipecat DAG.
    Fulfills PRD Directive 4:
    - Captures T0 when the user stops speaking (UserStoppedSpeakingFrame).
    - Captures T1 when the first audio frame is emitted (TTSAudioRawFrame / AudioRawFrame).
    - Computes TTFA latency = T1 - T0.
    - Immediately pushes TTFAMetric to IQueuePublisher asynchronously with zero audio drag.
    """

    def __init__(
        self,
        trace_id: str,
        mode: PipelineMode,
        queue_publisher: IQueuePublisher,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._trace_id = trace_id
        self._mode = mode
        self._queue = queue_publisher

        self._t0_ms: Optional[float] = None
        self._t1_ms: Optional[float] = None
        self._ttfa_recorded: bool = False
        self._computed_ttfa_ms: Optional[float] = None

        self._transcription: Optional[str] = None
        self._response_chunks: List[str] = []
        self._lock = asyncio.Lock()
        self.response_finished = asyncio.Event()

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def computed_ttfa_ms(self) -> Optional[float]:
        return self._computed_ttfa_ms

    @property
    def transcription(self) -> Optional[str]:
        return self._transcription

    @property
    def response_text(self) -> str:
        return " ".join(chunk.strip() for chunk in self._response_chunks).strip()

    def set_t0_timestamp(self, t0_ms: float) -> None:
        """Explicitly set T0 marker (useful in discrete file tests)."""
        self._t0_ms = t0_ms

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process incoming frame, capture telemetry, and pass downstream immediately."""
        await super().process_frame(frame, direction)

        now_ms = time.time() * 1000

        # 1. Capture T0: User stopped speaking
        if isinstance(frame, (UserStoppedSpeakingFrame, VADUserStoppedSpeakingFrame)):
            self._t0_ms = now_ms
            logger.debug(f"[{self._trace_id}] T0 captured (UserStoppedSpeaking): {self._t0_ms:.2f}ms")
            event = TelemetryEvent(
                trace_id=self._trace_id,
                event_type=TelemetryEventType.USER_STOPPED_SPEAKING,
                timestamp_ms=self._t0_ms,
            )
            asyncio.create_task(self._queue.push_event(event))

        # 2. Capture User Transcription
        elif isinstance(frame, TranscriptionFrame):
            self._transcription = frame.text
            event = TelemetryEvent(
                trace_id=self._trace_id,
                event_type=TelemetryEventType.STT_OUTPUT,
                timestamp_ms=now_ms,
                payload={"text": frame.text},
            )
            asyncio.create_task(self._queue.push_event(event))

        # 3. Capture LLM response tokens
        elif isinstance(frame, TTSTextFrame):
            if hasattr(frame, "text") and frame.text:
                self._response_chunks.append(frame.text)

        # 4. Capture T1 & TTFA: First synthesized or output audio frame
        elif isinstance(frame, (TTSAudioRawFrame, OutputAudioRawFrame)):
            if self._t0_ms is not None and not self._ttfa_recorded:
                self._t1_ms = now_ms
                self._ttfa_recorded = True
                ttfa = max(0.0, round(self._t1_ms - self._t0_ms, 2))
                self._computed_ttfa_ms = ttfa
                logger.info(f"[{self._trace_id}] TTFA captured: {ttfa:.2f}ms (Mode: {self._mode.value})")

                metric = TTFAMetric(
                    trace_id=self._trace_id,
                    mode=self._mode,
                    t0_timestamp_ms=self._t0_ms,
                    t1_timestamp_ms=self._t1_ms,
                    ttfa_ms=ttfa,
                )
                # Non-invasive outbox push via background task
                asyncio.create_task(self._queue.push_metric(metric))

        elif isinstance(frame, LLMFullResponseEndFrame):
            if self._computed_ttfa_ms is not None:
                self.response_finished.set()

        # 5. Handle interruption or new turn start: reset turn markers
        elif isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame, InterruptionFrame)):
            self._t0_ms = None
            self._t1_ms = None
            self._ttfa_recorded = False

        # Always push frame downstream immediately so there is zero audio drag
        await self.push_frame(frame, direction)
