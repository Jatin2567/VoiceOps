"""Driving adapter: Telemetry & Observability API routes."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.dependencies import get_telemetry_repository
from backend.domain.models.benchmark import BenchmarkResult
from backend.domain.ports.telemetry_repository import ITelemetryRepository

router = APIRouter(prefix="/telemetry", tags=["Telemetry & Observability"])


@router.get(
    "/{trace_id}",
    response_model=BenchmarkResult,
    summary="Get Benchmark Result by Trace ID",
    description="Pollable endpoint for Streamlit to inspect TTFA, status, and latency breakdown."
)
async def get_telemetry_by_trace(
    trace_id: str,
    repo: ITelemetryRepository = Depends(get_telemetry_repository),
) -> BenchmarkResult:
    """Retrieve benchmark metrics and TTFA outcome for a given trace_id."""
    result = await repo.get_benchmark_result(trace_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark trace '{trace_id}' not found.",
        )
    return result


@router.get(
    "/history/recent",
    response_model=List[BenchmarkResult],
    summary="List Recent Benchmarks",
    description="Retrieve recent benchmark runs for comparative analysis and audit ledger."
)
async def list_recent_benchmarks(
    limit: int = 25,
    repo: ITelemetryRepository = Depends(get_telemetry_repository),
) -> List[BenchmarkResult]:
    """Retrieve up to limit recent benchmark results."""
    return await repo.list_recent_benchmarks(limit=limit)
