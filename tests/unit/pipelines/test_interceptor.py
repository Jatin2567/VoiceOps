"""Unit tests for DeterministicSidecarInterceptor (Directive 5)."""
import unittest
from datetime import datetime, timezone

from pipecat.frames.frames import (
    AudioRawFrame,
    FunctionCallInProgressFrame,
    FunctionCallResultFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.domain.models.booking import Booking, BookingStatus, ServiceType
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository
from backend.pipelines.processors.interceptor import DeterministicSidecarInterceptor


class TestDeterministicSidecarInterceptor(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring sidecar interceptor enforces deterministic guardrails."""

    async def asyncSetUp(self):
        self.repo = MockBookingRepository(seed_sample_data=True)
        self.guardrail_service = GuardrailPolicyService(self.repo)
        self.interceptor = DeterministicSidecarInterceptor(
            trace_id="interceptor-trace-01",
            guardrail_service=self.guardrail_service,
        )

    async def test_tool_results_are_not_executed_a_second_time(self):
        frame = FunctionCallResultFrame(
            function_name="cancel_appointment", tool_call_id="already-handled",
            arguments={"booking_id": "book-001"}, result={"status": "success"},
        )
        await self.interceptor.process_frame(frame, FrameDirection.DOWNSTREAM)
        self.assertEqual(self.interceptor.interception_count, 0)
        self.assertNotEqual((await self.repo.get_booking("book-001")).status,
                            BookingStatus.CANCELLED)

    async def test_intercept_cancellation_allowed(self):
        """Verify valid cancellation tool call is intercepted and allowed."""
        call_frame = FunctionCallInProgressFrame(
            function_name="cancel_appointment",
            tool_call_id="call_cancel_1",
            arguments={"booking_id": "book-001"},
        )

        await self.interceptor.process_frame(call_frame, FrameDirection.DOWNSTREAM)

        self.assertEqual(self.interceptor.interception_count, 1)
        self.assertGreater(self.interceptor.total_overhead_ms, 0.0)

        # Booking should now be cancelled in the repository
        booking = await self.repo.get_booking("book-001")
        self.assertEqual(booking.status, BookingStatus.CANCELLED)

    async def test_intercept_cancellation_blocked(self):
        """Verify invalid cancellation (missing booking) is intercepted and blocked."""
        call_frame = FunctionCallInProgressFrame(
            function_name="cancel_appointment",
            tool_call_id="call_cancel_2",
            arguments={"booking_id": "nonexistent-id"},
        )

        await self.interceptor.process_frame(call_frame, FrameDirection.DOWNSTREAM)

        self.assertEqual(self.interceptor.interception_count, 1)
        self.assertGreater(len(self.interceptor.violations_detected), 0)
        self.assertIn("No booking found", self.interceptor.violations_detected[0])


if __name__ == "__main__":
    unittest.main()
