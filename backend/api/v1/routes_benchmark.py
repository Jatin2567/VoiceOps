"""Driving adapter: Benchmark execution API routes."""
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.dependencies import get_benchmark_runner
from backend.application.services.benchmark_runner import BenchmarkRunnerService
from backend.domain.models.benchmark import BenchmarkRequest, PipelineMode

router = APIRouter(prefix="/benchmark", tags=["Benchmark Operations"])


class TriggerBenchmarkPayload(BaseModel):
    """Payload for initiating a voice turn benchmark."""
    mode: PipelineMode = Field(
        default=PipelineMode.CASCADE,
        description="Architecture topology (cascade, hybrid)"
    )
    audio_file_path: Optional[str] = Field(
        default=None,
        description="Path to discrete .wav test asset"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session or caller identifier"
    )
    scenario_name: Optional[str] = Field(
        default="Standard Utterance",
        description="Descriptive scenario for testing"
    )


class TriggerBenchmarkResponse(BaseModel):
    """Instant acknowledgement response (Directive 2)."""
    trace_id: str
    status: str
    mode: str
    message: str


@router.get("/modes")
async def list_modes() -> List[Dict[str, Any]]:
    """List available architectural modes with their topology characteristics."""
    return [
        {
            "id": PipelineMode.CASCADE.value,
            "name": "Cascade (Groq Whisper + Groq LLM + Edge-TTS)",
            "description": "Discrete STT -> LLM -> TTS pipeline with high inspectability.",
            "features": ["Subprocess TTS pipe", "Independent stage metrics"],
        },
        {
            "id": PipelineMode.HYBRID.value,
            "name": "Hybrid (Groq + Edge-TTS + Guardrails)",
            "description": "Groq tool calls checked against clinic policy before Edge-TTS speaks the result.",
            "features": ["Deterministic policy enforcement", "Sidecar tool interception"],
        },
    ]


@router.post(
    "",
    response_model=TriggerBenchmarkResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Voice AI Benchmark Run",
    description="Fulfills Directive 2: Instantly returns 200 OK with a trace_id while pipeline processes in background."
)
async def trigger_benchmark(
    payload: TriggerBenchmarkPayload,
    runner: BenchmarkRunnerService = Depends(get_benchmark_runner),
) -> TriggerBenchmarkResponse:
    """
    Trigger a turn benchmark.
    Instantly returns trace_id; pipeline processes concurrently in background.
    """
    trace_id = str(uuid4())

    # Resolve audio file if none provided
    audio_path = payload.audio_file_path
    if not audio_path or not os.path.exists(audio_path):
        sample_path = os.path.join("frontend", "assets", "sample_booking.wav")
        if os.path.exists(sample_path):
            audio_path = sample_path

    request = BenchmarkRequest(
        trace_id=trace_id,
        mode=payload.mode,
        audio_file_path=audio_path,
        session_id=payload.session_id or f"session_{uuid4().hex[:8]}",
        metadata={"scenario": payload.scenario_name or "Custom Run"},
    )

    returned_trace = runner.start_benchmark(request)

    return TriggerBenchmarkResponse(
        trace_id=returned_trace,
        status="running",
        mode=payload.mode.value,
        message="Benchmark initiated asynchronously. Poll /v1/telemetry/{trace_id} for metrics.",
    )
