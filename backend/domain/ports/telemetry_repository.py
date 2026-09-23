"""Domain port for telemetry and benchmark persistence (e.g. Supabase PostgreSQL)."""
from abc import ABC, abstractmethod
from typing import List, Optional

from backend.domain.models.benchmark import BenchmarkResult
from backend.domain.models.telemetry import TelemetryEvent, TTFAMetric


class ITelemetryRepository(ABC):
    """Abstract port for persisting telemetry events, TTFA metrics, and benchmark results."""

    @abstractmethod
    async def save_metric(self, metric: TTFAMetric) -> None:
        """Persist a single TTFA metric record."""
        raise NotImplementedError

    @abstractmethod
    async def save_metrics_batch(self, metrics: List[TTFAMetric]) -> None:
        """Persist a batch of TTFA metrics atomically."""
        raise NotImplementedError

    @abstractmethod
    async def save_event(self, event: TelemetryEvent) -> None:
        """Persist a granular telemetry event."""
        raise NotImplementedError

    @abstractmethod
    async def save_benchmark_result(self, result: BenchmarkResult) -> None:
        """Persist or update an aggregated benchmark outcome."""
        raise NotImplementedError

    @abstractmethod
    async def get_benchmark_result(self, trace_id: str) -> Optional[BenchmarkResult]:
        """Retrieve the benchmark result by trace ID."""
        raise NotImplementedError

    @abstractmethod
    async def list_recent_benchmarks(self, limit: int = 50) -> List[BenchmarkResult]:
        """List recently executed benchmarks for UI dashboards and analytics."""
        raise NotImplementedError
