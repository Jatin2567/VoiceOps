"""Domain models for deterministic guardrail evaluation and sidecar interception."""
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class GuardrailAction(str, Enum):
    """Action directive returned by the deterministic sidecar."""
    ALLOW = "allow"    # Proceed with function execution
    MODIFY = "modify"  # Parameters sanitized/corrected before execution
    BLOCK = "block"    # Block execution and return deterministic policy error


class PolicyType(str, Enum):
    """Categorization of deterministic policy rules."""
    SLOT_UNAVAILABLE = "slot_unavailable"
    OUTSIDE_BUSINESS_HOURS = "outside_business_hours"
    INVALID_CONTACT_INFO = "invalid_contact_info"
    DOUBLE_BOOKING_PREVENTION = "double_booking_prevention"
    UNAUTHORIZED_TOOL = "unauthorized_tool"
    MALFORMED_ARGUMENTS = "malformed_arguments"


class PolicyViolation(BaseModel):
    """Representation of an individual policy breach."""
    policy_type: PolicyType = Field(..., description="Category of rule breached")
    message: str = Field(..., description="Human/LLM understandable explanation")
    remedy_suggestion: Optional[str] = Field(
        default=None,
        description="Suggested correction or alternate slot"
    )


class GuardrailEvaluationRequest(BaseModel):
    """Payload passed to GuardrailService when FunctionCallFrame is intercepted."""
    trace_id: str = Field(..., description="Trace correlation ID")
    function_name: str = Field(..., description="Target tool/function name called by the LLM")
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw arguments provided by the model"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual metadata (e.g. caller identity, conversation history)"
    )


class GuardrailEvaluationResult(BaseModel):
    """Result of deterministic policy guardrail evaluation."""
    evaluation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Evaluation trace identifier"
    )
    action: GuardrailAction = Field(
        default=GuardrailAction.ALLOW,
        description="Directive to allow, modify, or block"
    )
    is_allowed: bool = Field(
        default=True,
        description="Convenience boolean flag indicating if tool execution may proceed"
    )
    function_name: str = Field(
        ...,
        description="Name of the evaluated function"
    )
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Approved or sanitized arguments"
    )
    violations: List[PolicyViolation] = Field(
        default_factory=list,
        description="Detected policy violations"
    )
    feedback_to_agent: Optional[str] = Field(
        default=None,
        description="Deterministic error/rejection message to feed back into FunctionReturnFrame"
    )
    overhead_ms: float = Field(
        default=0.0,
        description="Latency overhead introduced by evaluating the policy in ms"
    )
