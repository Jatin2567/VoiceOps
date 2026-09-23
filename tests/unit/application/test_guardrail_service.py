"""Unit tests for GuardrailPolicyService application service."""
import unittest
from datetime import datetime, timezone

from backend.application.services.guardrail_service import GuardrailPolicyService
from backend.domain.models.guardrail import GuardrailAction, GuardrailEvaluationRequest, PolicyType
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository


class TestGuardrailService(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring deterministic policy evaluation logic."""

    async def asyncSetUp(self):
        self.repo = MockBookingRepository(seed_sample_data=True)
        self.service = GuardrailPolicyService(self.repo)

    async def test_schedule_valid_appointment(self):
        """Verify scheduling an available slot succeeds."""
        req = GuardrailEvaluationRequest(
            trace_id="gr-test-1",
            function_name="schedule_appointment",
            arguments={
                "customer_name": "David Miller",
                "customer_phone": "5559876543",
                "slot_time": "2026-09-28T14:00:00Z",
                "service_type": "consultation",
            },
        )
        res = await self.service.evaluate_tool_call(req)
        self.assertTrue(res.is_allowed)
        self.assertEqual(res.action, GuardrailAction.ALLOW)
        self.assertIn("booking_id", res.arguments)
        self.assertGreater(res.overhead_ms, 0.0)

    async def test_schedule_slot_conflict_blocked(self):
        """Verify scheduling an occupied slot triggers SLOT_UNAVAILABLE violation."""
        # book-001 is seeded at 2026-09-25T10:00:00Z for consultation
        req = GuardrailEvaluationRequest(
            trace_id="gr-test-2",
            function_name="schedule_appointment",
            arguments={
                "customer_name": "Eve Adams",
                "customer_phone": "5551112233",
                "slot_time": "2026-09-25T10:00:00Z",
                "service_type": "consultation",
            },
        )
        res = await self.service.evaluate_tool_call(req)
        self.assertFalse(res.is_allowed)
        self.assertEqual(res.action, GuardrailAction.BLOCK)
        self.assertEqual(len(res.violations), 1)
        self.assertEqual(res.violations[0].policy_type, PolicyType.SLOT_UNAVAILABLE)

    async def test_schedule_invalid_phone_blocked(self):
        """Verify phone with fewer than 10 digits is rejected."""
        req = GuardrailEvaluationRequest(
            trace_id="gr-test-3",
            function_name="schedule_appointment",
            arguments={
                "customer_name": "Frank",
                "customer_phone": "123",
                "slot_time": "2026-09-29T10:00:00Z",
                "service_type": "consultation",
            },
        )
        res = await self.service.evaluate_tool_call(req)
        self.assertFalse(res.is_allowed)
        self.assertEqual(res.action, GuardrailAction.BLOCK)
        self.assertEqual(res.violations[0].policy_type, PolicyType.INVALID_CONTACT_INFO)

    async def test_cancel_nonexistent_booking_blocked(self):
        """Verify cancelling unknown booking is blocked."""
        req = GuardrailEvaluationRequest(
            trace_id="gr-test-4",
            function_name="cancel_appointment",
            arguments={"booking_id": "nonexistent-book-id"},
        )
        res = await self.service.evaluate_tool_call(req)
        self.assertFalse(res.is_allowed)
        self.assertEqual(res.action, GuardrailAction.BLOCK)

    async def test_cancel_valid_booking_allowed(self):
        """Verify cancelling seeded booking book-002 is allowed."""
        req = GuardrailEvaluationRequest(
            trace_id="gr-test-5",
            function_name="cancel_appointment",
            arguments={"booking_id": "book-002"},
        )
        res = await self.service.evaluate_tool_call(req)
        self.assertTrue(res.is_allowed)
        self.assertEqual(res.action, GuardrailAction.ALLOW)

    async def test_unauthorized_tool_blocked(self):
        """Verify unapproved tool is blocked."""
        req = GuardrailEvaluationRequest(
            trace_id="gr-test-6",
            function_name="delete_all_database_records",
            arguments={},
        )
        res = await self.service.evaluate_tool_call(req)
        self.assertFalse(res.is_allowed)
        self.assertEqual(res.action, GuardrailAction.BLOCK)
        self.assertEqual(res.violations[0].policy_type, PolicyType.UNAUTHORIZED_TOOL)


if __name__ == "__main__":
    unittest.main()
