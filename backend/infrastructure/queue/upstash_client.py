"""Upstash Redis queue driven adapter for the telemetry Outbox pattern."""
import asyncio
import json
import os
from typing import List, Optional

from loguru import logger

from backend.domain.models.telemetry import TelemetryEvent, TTFAMetric
from backend.domain.ports.queue_publisher import IQueuePublisher


class UpstashQueuePublisher(IQueuePublisher):
    """
    Driven adapter implementing IQueuePublisher.
    Supports Upstash Redis via REST (UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN),
    standard Redis connection (REDIS_URL), or an async in-memory deque fallback for offline testing.
    """

    METRICS_QUEUE_KEY = "voiceops:outbox:metrics"
    EVENTS_QUEUE_KEY = "voiceops:outbox:events"

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        redis_url: Optional[str] = None,
    ):
        self.url = url or os.getenv("UPSTASH_REDIS_REST_URL")
        self.token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN")
        self.redis_url = redis_url or os.getenv("REDIS_URL")

        self._upstash_client = None
        self._standard_redis = None
        self._in_memory_metrics: List[str] = []
        self._in_memory_events: List[str] = []
        self._lock = asyncio.Lock()

        # 1. Attempt Upstash REST client
        if self.url and self.token and "upstash.io" in self.url:
            try:
                from upstash_redis.asyncio import Redis as AsyncUpstashRedis
                self._upstash_client = AsyncUpstashRedis(url=self.url, token=self.token)
                logger.info("Upstash Redis REST client initialized.")
            except Exception as e:
                logger.warning(f"Could not initialize Upstash REST client: {e}")

        # 2. Attempt standard Redis client if Upstash REST not initialized
        if not self._upstash_client and self.redis_url:
            try:
                import redis.asyncio as aioredis
                self._standard_redis = aioredis.from_url(self.redis_url, decode_responses=True)
                logger.info("Standard Redis client initialized from REDIS_URL.")
            except Exception as e:
                logger.warning(f"Could not initialize standard Redis: {e}")

        if not self._upstash_client and not self._standard_redis:
            logger.info("Using in-memory queue fallback for outbox pattern.")

    async def push_metric(self, metric: TTFAMetric) -> None:
        """Push a TTFA metric into the outbox queue via LPUSH."""
        serialized = metric.model_dump_json()

        if self._upstash_client:
            try:
                await self._upstash_client.lpush(self.METRICS_QUEUE_KEY, serialized)
                return
            except Exception as e:
                logger.error(f"Upstash push_metric error: {e}. Appending to in-memory fallback.")

        if self._standard_redis:
            try:
                await self._standard_redis.lpush(self.METRICS_QUEUE_KEY, serialized)
                return
            except Exception as e:
                logger.error(f"Redis push_metric error: {e}. Appending to in-memory fallback.")

        async with self._lock:
            self._in_memory_metrics.insert(0, serialized)

    async def push_event(self, event: TelemetryEvent) -> None:
        """Push a telemetry event into the outbox queue via LPUSH."""
        serialized = event.model_dump_json()

        if self._upstash_client:
            try:
                await self._upstash_client.lpush(self.EVENTS_QUEUE_KEY, serialized)
                return
            except Exception as e:
                logger.error(f"Upstash push_event error: {e}. Appending to in-memory fallback.")

        if self._standard_redis:
            try:
                await self._standard_redis.lpush(self.EVENTS_QUEUE_KEY, serialized)
                return
            except Exception as e:
                logger.error(f"Redis push_event error: {e}. Appending to in-memory fallback.")

        async with self._lock:
            self._in_memory_events.insert(0, serialized)

    async def pop_metrics(self, batch_size: int = 50) -> List[TTFAMetric]:
        """Pop up to batch_size metrics from the outbox queue via RPOP."""
        metrics: List[TTFAMetric] = []

        if self._upstash_client:
            try:
                # Upstash supports rpop with count in newer versions, or loop
                items = await self._upstash_client.rpop(self.METRICS_QUEUE_KEY, count=batch_size)
                if items:
                    if isinstance(items, (str, bytes)):
                        items = [items]
                    for item in items:
                        metrics.append(TTFAMetric.model_validate_json(item))
                return metrics
            except Exception as e:
                logger.error(f"Upstash pop_metrics error: {e}")

        if self._standard_redis:
            try:
                items = await self._standard_redis.rpop(self.METRICS_QUEUE_KEY, count=batch_size)
                if items:
                    if isinstance(items, (str, bytes)):
                        items = [items]
                    for item in items:
                        metrics.append(TTFAMetric.model_validate_json(item))
                return metrics
            except Exception as e:
                logger.error(f"Redis pop_metrics error: {e}")

        async with self._lock:
            popped_items: List[str] = []
            for _ in range(min(batch_size, len(self._in_memory_metrics))):
                popped_items.append(self._in_memory_metrics.pop())
            for item in popped_items:
                metrics.append(TTFAMetric.model_validate_json(item))
            return metrics

    async def pop_events(self, batch_size: int = 50) -> List[TelemetryEvent]:
        """Pop up to batch_size events from the outbox queue."""
        events: List[TelemetryEvent] = []

        if self._upstash_client:
            try:
                items = await self._upstash_client.rpop(self.EVENTS_QUEUE_KEY, count=batch_size)
                if items:
                    if isinstance(items, (str, bytes)):
                        items = [items]
                    for item in items:
                        events.append(TelemetryEvent.model_validate_json(item))
                return events
            except Exception as e:
                logger.error(f"Upstash pop_events error: {e}")

        if self._standard_redis:
            try:
                items = await self._standard_redis.rpop(self.EVENTS_QUEUE_KEY, count=batch_size)
                if items:
                    if isinstance(items, (str, bytes)):
                        items = [items]
                    for item in items:
                        events.append(TelemetryEvent.model_validate_json(item))
                return events
            except Exception as e:
                logger.error(f"Redis pop_events error: {e}")

        async with self._lock:
            popped_items: List[str] = []
            for _ in range(min(batch_size, len(self._in_memory_events))):
                popped_items.append(self._in_memory_events.pop())
            for item in popped_items:
                events.append(TelemetryEvent.model_validate_json(item))
            return events

    async def get_queue_depth(self) -> int:
        """Return total pending items in both metrics and events outbox queues."""
        total = 0
        if self._upstash_client:
            try:
                m_len = await self._upstash_client.llen(self.METRICS_QUEUE_KEY) or 0
                e_len = await self._upstash_client.llen(self.EVENTS_QUEUE_KEY) or 0
                return int(m_len) + int(e_len)
            except Exception as e:
                logger.error(f"Upstash get_queue_depth error: {e}")

        if self._standard_redis:
            try:
                m_len = await self._standard_redis.llen(self.METRICS_QUEUE_KEY) or 0
                e_len = await self._standard_redis.llen(self.EVENTS_QUEUE_KEY) or 0
                return int(m_len) + int(e_len)
            except Exception as e:
                logger.error(f"Redis get_queue_depth error: {e}")

        async with self._lock:
            return len(self._in_memory_metrics) + len(self._in_memory_events)
