"""Supabase persistence adapter for telemetry and benchmark results."""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.domain.models.benchmark import BenchmarkResult, BenchmarkStatus, LatencyBreakdown, PipelineMode
from backend.domain.models.telemetry import TelemetryEvent, TTFAMetric
from backend.domain.ports.telemetry_repository import ITelemetryRepository


class SupabaseTelemetryRepository(ITelemetryRepository):
    """
    Driven adapter implementing ITelemetryRepository against Supabase PostgreSQL.
    Provides automated fallback to in-memory persistence when Supabase credentials
    are not configured, ensuring zero crashes in local testing environments.
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        self._client = None
        self._in_memory_metrics: Dict[str, TTFAMetric] = {}
        self._in_memory_results: Dict[str, BenchmarkResult] = {}
        self._in_memory_events: List[TelemetryEvent] = []

        if self.supabase_url and self.supabase_key:
            try:
                from supabase import Client, create_client
                self._client: Optional[Client] = create_client(self.supabase_url, self.supabase_key)
                logger.info("Supabase client initialized successfully.")
            except Exception as e:
                logger.warning(f"Failed to initialize Supabase client: {e}. Falling back to in-memory mode.")
                self._client = None
        else:
            logger.info("Supabase credentials not provided. Using in-memory telemetry storage fallback.")

    @property
    def is_connected(self) -> bool:
        """Return True if real Supabase client is active."""
        return self._client is not None

    async def save_metric(self, metric: TTFAMetric) -> None:
        """Persist a single TTFA metric record."""
        data = {
            "trace_id": metric.trace_id,
            "mode": metric.mode.value,
            "t0_timestamp_ms": metric.t0_timestamp_ms,
            "t1_timestamp_ms": metric.t1_timestamp_ms,
            "ttfa_ms": metric.ttfa_ms,
            "recorded_at": metric.recorded_at.isoformat(),
        }

        if self._client:
            try:
                self._client.table("ttfa_metrics").insert(data).execute()
                return
            except Exception as e:
                logger.error(f"Supabase insert failed for metric {metric.trace_id}: {e}. Storing locally.")

        self._in_memory_metrics[metric.trace_id] = metric

    async def save_metrics_batch(self, metrics: List[TTFAMetric]) -> None:
        """Persist a batch of TTFA metrics."""
        if not metrics:
            return

        data_rows = [
            {
                "trace_id": m.trace_id,
                "mode": m.mode.value,
                "t0_timestamp_ms": m.t0_timestamp_ms,
                "t1_timestamp_ms": m.t1_timestamp_ms,
                "ttfa_ms": m.ttfa_ms,
                "recorded_at": m.recorded_at.isoformat(),
            }
            for m in metrics
        ]

        if self._client:
            try:
                self._client.table("ttfa_metrics").insert(data_rows).execute()
                return
            except Exception as e:
                logger.error(f"Supabase batch insert failed: {e}. Storing in memory fallback.")

        for m in metrics:
            self._in_memory_metrics[m.trace_id] = m

    async def save_event(self, event: TelemetryEvent) -> None:
        """Persist a granular pipeline telemetry event."""
        data = {
            "event_id": event.event_id,
            "trace_id": event.trace_id,
            "event_type": event.event_type.value,
            "timestamp_ms": event.timestamp_ms,
            "payload": json.dumps(event.payload),
        }

        if self._client:
            try:
                self._client.table("telemetry_events").insert(data).execute()
                return
            except Exception as e:
                logger.error(f"Supabase event insert failed: {e}. Storing locally.")

        self._in_memory_events.append(event)

    async def save_benchmark_result(self, result: BenchmarkResult) -> None:
        """Persist or update an aggregated benchmark outcome."""
        data = {
            "trace_id": result.trace_id,
            "mode": result.mode.value,
            "status": result.status.value,
            "ttfa_ms": result.ttfa_ms,
            "breakdown": result.breakdown.model_dump(),
            "transcription": result.transcription,
            "response_text": result.response_text,
            "guardrail_violations": result.guardrail_violations,
            "interception_count": result.interception_count,
            "error_message": result.error_message,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        }

        if self._client:
            try:
                self._client.table("benchmark_results").upsert(data, on_conflict="trace_id").execute()
                return
            except Exception as e:
                logger.error(f"Supabase upsert failed for benchmark {result.trace_id}: {e}. Storing in-memory.")

        self._in_memory_results[result.trace_id] = result.model_copy()

    async def get_benchmark_result(self, trace_id: str) -> Optional[BenchmarkResult]:
        """Retrieve benchmark result by trace ID."""
        if self._client:
            try:
                response = self._client.table("benchmark_results").select("*").eq("trace_id", trace_id).execute()
                if response.data and len(response.data) > 0:
                    row = response.data[0]
                    return BenchmarkResult(
                        trace_id=row["trace_id"],
                        mode=PipelineMode(row["mode"]),
                        status=BenchmarkStatus(row["status"]),
                        ttfa_ms=row.get("ttfa_ms"),
                        breakdown=LatencyBreakdown(**(row.get("breakdown") or {})),
                        transcription=row.get("transcription"),
                        response_text=row.get("response_text"),
                        guardrail_violations=row.get("guardrail_violations") or [],
                        interception_count=row.get("interception_count") or 0,
                        error_message=row.get("error_message"),
                        completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
                    )
            except Exception as e:
                logger.error(f"Failed to query Supabase for trace {trace_id}: {e}.")

        return self._in_memory_results.get(trace_id)

    async def list_recent_benchmarks(self, limit: int = 50) -> List[BenchmarkResult]:
        """List recently recorded benchmark results."""
        if self._client:
            try:
                response = (
                    self._client.table("benchmark_results")
                    .select("*")
                    .order("completed_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                results: List[BenchmarkResult] = []
                for row in response.data or []:
                    results.append(
                        BenchmarkResult(
                            trace_id=row["trace_id"],
                            mode=PipelineMode(row["mode"]),
                            status=BenchmarkStatus(row["status"]),
                            ttfa_ms=row.get("ttfa_ms"),
                            breakdown=LatencyBreakdown(**(row.get("breakdown") or {})),
                            transcription=row.get("transcription"),
                            response_text=row.get("response_text"),
                            guardrail_violations=row.get("guardrail_violations") or [],
                            interception_count=row.get("interception_count") or 0,
                            error_message=row.get("error_message"),
                            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
                        )
                    )
                return results
            except Exception as e:
                logger.error(f"Failed to list Supabase benchmarks: {e}.")

        # In-memory sorted by completed_at desc
        return sorted(
            list(self._in_memory_results.values()),
            key=lambda x: x.completed_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )[:limit]
