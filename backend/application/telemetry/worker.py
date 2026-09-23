"""Background Outbox worker flushing queued metrics from Redis to Supabase."""
import asyncio
from typing import Optional

from loguru import logger

from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.domain.ports.telemetry_repository import ITelemetryRepository


class TelemetryFlushWorker:
    """
    Background Outbox worker fulfilling PRD Directive 4:
    Periodically pops TTFAMetric and TelemetryEvent batches from the asynchronous
    queue (Upstash Redis) and flushes them to persistence (Supabase PostgreSQL),
    decoupling database I/O latency completely from the real-time audio pipeline.
    """

    def __init__(
        self,
        queue_publisher: IQueuePublisher,
        telemetry_repository: ITelemetryRepository,
        batch_size: int = 50,
        poll_interval_secs: float = 0.5,
    ):
        self.queue = queue_publisher
        self.repo = telemetry_repository
        self.batch_size = batch_size
        self.poll_interval = poll_interval_secs

        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start the background flush loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="telemetry_flush_worker")
        logger.info(
            f"TelemetryFlushWorker started (batch_size={self.batch_size}, "
            f"interval={self.poll_interval}s)"
        )

    async def stop(self) -> None:
        """Gracefully stop the worker and flush remaining items."""
        if not self._running:
            return
        logger.info("Stopping TelemetryFlushWorker and flushing residual queue...")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Final residual flush
        await self.flush_once()

    async def flush_once(self) -> int:
        """
        Execute a single flush cycle.
        Returns the number of metrics and events flushed.
        """
        flushed_count = 0
        try:
            # 1. Flush TTFA metrics
            metrics = await self.queue.pop_metrics(batch_size=self.batch_size)
            if metrics:
                await self.repo.save_metrics_batch(metrics)
                flushed_count += len(metrics)
                logger.debug(f"Flushed {len(metrics)} TTFA metrics to persistence.")

            # 2. Flush pipeline events
            events = await self.queue.pop_events(batch_size=self.batch_size)
            if events:
                for event in events:
                    await self.repo.save_event(event)
                flushed_count += len(events)
                logger.debug(f"Flushed {len(events)} telemetry events to persistence.")

        except Exception as e:
            logger.error(f"Error during telemetry flush cycle: {e}")

        return flushed_count

    async def _loop(self) -> None:
        """Internal asynchronous polling loop."""
        while self._running:
            try:
                await self.flush_once()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in TelemetryFlushWorker loop: {e}")
                await asyncio.sleep(self.poll_interval)
