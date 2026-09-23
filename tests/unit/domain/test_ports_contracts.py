"""Unit tests validating abstract port contracts and Hexagonal boundary enforcement."""
import inspect
import unittest
from datetime import datetime
from typing import AsyncGenerator, List, Optional

from backend.domain.models.benchmark import BenchmarkRequest, BenchmarkResult, PipelineMode
from backend.domain.models.booking import Booking, BookingStatus, ServiceType
from backend.domain.models.guardrail import GuardrailEvaluationRequest, GuardrailEvaluationResult
from backend.domain.models.telemetry import TelemetryEvent, TTFAMetric
from backend.domain.ports.booking_repository import IBookingRepository
from backend.domain.ports.guardrail_policy import IGuardrailPolicyService
from backend.domain.ports.queue_publisher import IQueuePublisher
from backend.domain.ports.telemetry_repository import ITelemetryRepository
from backend.domain.ports.voice_pipeline import IVoicePipeline


class TestPortsContracts(unittest.TestCase):
    """Test suite ensuring all domain ports enforce abstract method implementation."""

    def test_abstract_ports_cannot_be_instantiated_directly(self):
        """Verify TypeError is raised when instantiating abstract ports."""
        with self.assertRaises(TypeError):
            IBookingRepository()

        with self.assertRaises(TypeError):
            ITelemetryRepository()

        with self.assertRaises(TypeError):
            IQueuePublisher()

        with self.assertRaises(TypeError):
            IVoicePipeline()

        with self.assertRaises(TypeError):
            IGuardrailPolicyService()

    def test_booking_repository_concrete_implementation(self):
        """Verify concrete implementation satisfying IBookingRepository contract."""
        class MockBookingRepo(IBookingRepository):
            def __init__(self):
                self._storage = {}

            async def get_booking(self, booking_id: str) -> Optional[Booking]:
                return self._storage.get(booking_id)

            async def create_booking(self, booking: Booking) -> Booking:
                self._storage[booking.id] = booking
                return booking

            async def cancel_booking(self, booking_id: str) -> bool:
                if booking_id in self._storage:
                    self._storage[booking_id].status = BookingStatus.CANCELLED
                    return True
                return False

            async def check_slot_available(
                self, slot_time: datetime, service_type: ServiceType
            ) -> bool:
                return True

            async def list_bookings(
                self, status: Optional[BookingStatus] = None
            ) -> List[Booking]:
                return list(self._storage.values())

        repo = MockBookingRepo()
        self.assertIsInstance(repo, IBookingRepository)

    def test_queue_publisher_concrete_implementation(self):
        """Verify concrete implementation satisfying IQueuePublisher contract."""
        class MockQueue(IQueuePublisher):
            def __init__(self):
                self.metrics = []
                self.events = []

            async def push_metric(self, metric: TTFAMetric) -> None:
                self.metrics.append(metric)

            async def push_event(self, event: TelemetryEvent) -> None:
                self.events.append(event)

            async def pop_metrics(self, batch_size: int = 50) -> List[TTFAMetric]:
                popped = self.metrics[:batch_size]
                self.metrics = self.metrics[batch_size:]
                return popped

            async def pop_events(self, batch_size: int = 50) -> List[TelemetryEvent]:
                popped = self.events[:batch_size]
                self.events = self.events[batch_size:]
                return popped

            async def get_queue_depth(self) -> int:
                return len(self.metrics) + len(self.events)

        queue = MockQueue()
        self.assertIsInstance(queue, IQueuePublisher)

    def test_guardrail_policy_concrete_implementation(self):
        """Verify concrete implementation satisfying IGuardrailPolicyService contract."""
        class MockGuardrailService(IGuardrailPolicyService):
            async def evaluate_tool_call(
                self, request: GuardrailEvaluationRequest
            ) -> GuardrailEvaluationResult:
                return GuardrailEvaluationResult(
                    function_name=request.function_name,
                    is_allowed=True
                )

        service = MockGuardrailService()
        self.assertIsInstance(service, IGuardrailPolicyService)


if __name__ == "__main__":
    unittest.main()
