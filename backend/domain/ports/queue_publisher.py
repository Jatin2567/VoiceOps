"""Domain port defining the asynchronous queue contract (e.g. Upstash Redis Outbox)."""
from abc import ABC, abstractmethod
from typing import List

from backend.domain.models.telemetry import TelemetryEvent, TTFAMetric


class IQueuePublisher(ABC):
    """Abstract port for non-blocking outbox queue push and pop operations."""

    @abstractmethod
    async def push_metric(self, metric: TTFAMetric) -> None:
        """Push a TTFA metric into the outbox queue (e.g. via LPUSH)."""
        raise NotImplementedError

    @abstractmethod
    async def push_event(self, event: TelemetryEvent) -> None:
        """Push a granular pipeline telemetry event into the outbox queue."""
        raise NotImplementedError

    @abstractmethod
    async def pop_metrics(self, batch_size: int = 50) -> List[TTFAMetric]:
        """Pop up to batch_size metrics from the queue for worker ingestion (e.g. via RPOP)."""
        raise NotImplementedError

    @abstractmethod
    async def pop_events(self, batch_size: int = 50) -> List[TelemetryEvent]:
        """Pop up to batch_size events from the queue for worker ingestion."""
        raise NotImplementedError

    @abstractmethod
    async def get_queue_depth(self) -> int:
        """Return the current count of pending items in the queue."""
        raise NotImplementedError
