"""Unit tests for Guardrail domain models."""
import unittest

from backend.domain.models.guardrail import (
    GuardrailAction,
    GuardrailEvaluationRequest,
    GuardrailEvaluationResult,
    PolicyType,
    PolicyViolation,
)


class TestGuardrailModels(unittest.TestCase):
    """Test suite for guardrail and sidecar evaluation domain models."""

    def test_guardrail_actions(self):
        """Verify action enum values."""
        self.assertEqual(GuardrailAction.ALLOW.value, "allow")
        self.assertEqual(GuardrailAction.MODIFY.value, "modify")
        self.assertEqual(GuardrailAction.BLOCK.value, "block")

    def test_evaluation_request(self):
        """Verify GuardrailEvaluationRequest attributes."""
        req = GuardrailEvaluationRequest(
            trace_id="gr-trace-1",
            function_name="schedule_appointment",
            arguments={"slot": "2026-09-25T14:00:00Z", "phone": "5551234567"},
            context={"customer_id": "cust-88"}
        )
        self.assertEqual(req.trace_id, "gr-trace-1")
        self.assertEqual(req.function_name, "schedule_appointment")
        self.assertEqual(req.arguments["phone"], "5551234567")

    def test_evaluation_result_block_with_violations(self):
        """Verify blocked result structure and policy violation reporting."""
        violation = PolicyViolation(
            policy_type=PolicyType.SLOT_UNAVAILABLE,
            message="Requested slot 14:00 is already reserved.",
            remedy_suggestion="Suggest 15:00 instead."
        )
        result = GuardrailEvaluationResult(
            action=GuardrailAction.BLOCK,
            is_allowed=False,
            function_name="schedule_appointment",
            violations=[violation],
            feedback_to_agent="Error: Slot 14:00 unavailable. Suggest 15:00.",
            overhead_ms=12.4
        )
        self.assertFalse(result.is_allowed)
        self.assertEqual(result.action, GuardrailAction.BLOCK)
        self.assertEqual(len(result.violations), 1)
        self.assertEqual(result.violations[0].policy_type, PolicyType.SLOT_UNAVAILABLE)
        self.assertEqual(result.overhead_ms, 12.4)
        self.assertIsNotNone(result.evaluation_id)


if __name__ == "__main__":
    unittest.main()
