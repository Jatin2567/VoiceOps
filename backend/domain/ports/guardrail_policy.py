"""Domain port defining the Guardrail Policy evaluation contract."""
from abc import ABC, abstractmethod

from backend.domain.models.guardrail import (
    GuardrailEvaluationRequest,
    GuardrailEvaluationResult,
)


class IGuardrailPolicyService(ABC):
    """Abstract port for evaluating deterministic policy rules during voice tool calls."""

    @abstractmethod
    async def evaluate_tool_call(
        self,
        request: GuardrailEvaluationRequest
    ) -> GuardrailEvaluationResult:
        """
        Evaluate a function call intercepted by the Pipecat sidecar.
        Inspects function name and arguments against operational rules and repository state.
        Returns whether to allow, modify, or block the call with feedback for the LLM.
        """
        raise NotImplementedError
