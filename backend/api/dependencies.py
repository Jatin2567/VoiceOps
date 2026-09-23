"""Dependency Injection wiring for Hexagonal Architecture ports and adapters."""
from typing import Optional

from backend.application.services.benchmark_runner import BenchmarkRunnerService
from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.application.telemetry.worker import TelemetryFlushWorker
from backend.domain.ports.booking_repository import IBookingRepository
from backend.domain.ports.guardrail_policy import IGuardrailPolicyService
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.domain.ports.telemetry_repository import ITelemetryRepository
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository
from backend.infrastructure.persistence.supabase_client import SupabaseTelemetryRepository
from backend.infrastructure.providers.gemini_live_client import GeminiLiveClient
from backend.infrastructure.queue.upstash_client import UpstashQueuePublisher
from backend.pipelines.factory import PipelineFactory


class ApplicationContainer:
    """Singleton IoC container wiring driving adapters to domain ports."""

    def __init__(self):
        # Persistence & Queue Driven Adapters
        self.booking_repo: IBookingRepository = MockBookingRepository(seed_sample_data=True)
        self.telemetry_repo: ITelemetryRepository = SupabaseTelemetryRepository()
        self.queue_publisher: IQueuePublisher = UpstashQueuePublisher()

        # Domain & Application Services
        self.guardrail_service: IGuardrailPolicyService = GuardrailPolicyService(self.booking_repo)
        self.gemini_client = GeminiLiveClient()

        # Pipeline DAG Factory
        self.pipeline_factory = PipelineFactory(
            queue_publisher=self.queue_publisher,
            guardrail_service=self.guardrail_service,
            gemini_client=self.gemini_client,
        )

        # Benchmark Orchestration Service
        self.benchmark_runner = BenchmarkRunnerService(
            pipeline_factory=self.pipeline_factory,
            telemetry_repository=self.telemetry_repo,
        )

        # Asynchronous Outbox Worker
        self.flush_worker = TelemetryFlushWorker(
            queue_publisher=self.queue_publisher,
            telemetry_repository=self.telemetry_repo,
            batch_size=50,
            poll_interval_secs=0.5,
        )


_container: Optional[ApplicationContainer] = None


def get_container() -> ApplicationContainer:
    """Return the initialized global dependency container."""
    global _container
    if _container is None:
        _container = ApplicationContainer()
    return _container


def get_benchmark_runner() -> BenchmarkRunnerService:
    """Dependency provider for BenchmarkRunnerService."""
    return get_container().benchmark_runner


def get_telemetry_repository() -> ITelemetryRepository:
    """Dependency provider for ITelemetryRepository."""
    return get_container().telemetry_repo


def get_booking_repository() -> IBookingRepository:
    """Dependency provider for IBookingRepository."""
    return get_container().booking_repo


def get_flush_worker() -> TelemetryFlushWorker:
    """Dependency provider for TelemetryFlushWorker."""
    return get_container().flush_worker
