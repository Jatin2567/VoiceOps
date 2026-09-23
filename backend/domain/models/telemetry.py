"""Domain models for telemetry and non-invasive TTFA capture."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from backend.domain.models.benchmark import PipelineMode


class TelemetryEventType(str, Enum):
    """Event types observed non-invasively within the Pipecat DAG."""
    USER_STARTED_SPEAKING = "user_started_speaking"
    USER_STOPPED_SPEAKING = "user_stopped_speaking"  # T0 marker
    STT_OUTPUT = "stt_output"
    LLM_FIRST_TOKEN = "llm_first_token"
    TTS_FIRST_AUDIO = "tts_first_audio"              # T1 marker (for Cascade)
    AUDIO_OUTPUT_STARTED = "audio_output_started"    # T1 marker (for Native/Hybrid)
    FUNCTION_CALL_INTERCEPTED = "function_call_intercepted"
    GUARDRAIL_EVALUATED = "guardrail_evaluated"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_ERROR = "pipeline_error"


class TTFAMetric(BaseModel):
    """
    Time-to-First-Audio (TTFA) observation.
    Captures T0 (UserStoppedSpeakingFrame) to T1 (AudioOutputFrame) latency in ms.
    """
    trace_id: str = Field(
        ...,
        description="Unique trace identifier associated with this turn"
    )
    mode: PipelineMode = Field(
        ...,
        description="Pipeline mode during this turn"
    )
    t0_timestamp_ms: float = Field(
        ...,
        description="Epoch timestamp in milliseconds when UserStoppedSpeakingFrame occurred"
    )
    t1_timestamp_ms: float = Field(
        ...,
        description="Epoch timestamp in milliseconds when first AudioOutputFrame occurred"
    )
    ttfa_ms: float = Field(
        default=0.0,
        description="Computed Time-to-First-Audio latency in milliseconds (T1 - T0)"
    )
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when metric was finalized"
    )

    @model_validator(mode="after")
    def compute_ttfa(self) -> "TTFAMetric":
        """Automatically calculate TTFA if not explicitly provided or if recalculated."""
        if self.t1_timestamp_ms >= self.t0_timestamp_ms:
            self.ttfa_ms = round(self.t1_timestamp_ms - self.t0_timestamp_ms, 2)
        else:
            self.ttfa_ms = 0.0
        return self


class TelemetryEvent(BaseModel):
    """Point-in-time telemetry event emitted during frame processing."""
    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique event ID"
    )
    trace_id: str = Field(
        ...,
        description="Correlation trace ID"
    )
    event_type: TelemetryEventType = Field(
        ...,
        description="Classification of the pipeline event"
    )
    timestamp_ms: float = Field(
        ...,
        description="Precise monotonic or epoch millisecond timestamp"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event payload (e.g. transcript text, token counts, function arguments)"
    )


class TelemetryBatch(BaseModel):
    """Batch container for metrics and events to flush through the Outbox queue."""
    batch_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Batch sequence identifier"
    )
    metrics: List[TTFAMetric] = Field(
        default_factory=list,
        description="List of TTFA metrics"
    )
    events: List[TelemetryEvent] = Field(
        default_factory=list,
        description="List of granular pipeline events"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Batch creation timestamp"
    )
