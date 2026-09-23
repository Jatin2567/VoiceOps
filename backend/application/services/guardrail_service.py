"""Deterministic Guardrail evaluation application service."""
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.domain.models.booking import Booking, BookingStatus, ServiceType
from backend.domain.models.guardrail import (
    GuardrailAction,
    GuardrailEvaluationRequest,
    GuardrailEvaluationResult,
    PolicyType,
    PolicyViolation,
)
from backend.domain.ports.booking_repository import IBookingRepository
from backend.domain.ports.guardrail_policy import IGuardrailPolicyService


class GuardrailPolicyService(IGuardrailPolicyService):
    """
    Application service implementing IGuardrailPolicyService.
    Performs deterministic evaluation of business rules and constraints
    against the booking repository without relying on stochastic LLM reasoning.
    """

    def __init__(self, booking_repository: IBookingRepository):
        self.booking_repo = booking_repository

    async def evaluate_tool_call(
        self,
        request: GuardrailEvaluationRequest
    ) -> GuardrailEvaluationResult:
        """
        Evaluate tool call function and arguments against deterministic clinic policy.
        """
        start_t = time.perf_counter()
        fn = request.function_name
        args = request.arguments

        logger.info(f"Evaluating deterministic guardrail for tool: {fn} (trace: {request.trace_id})")

        violations: List[PolicyViolation] = []
        action = GuardrailAction.ALLOW
        feedback: Optional[str] = None
        sanitized_args = dict(args)

        if fn == "cancel_appointment":
            action, feedback, violations = await self._evaluate_cancellation(args)
        elif fn == "schedule_appointment":
            action, feedback, violations, sanitized_args = await self._evaluate_scheduling(args)
        elif fn == "check_slot_availability":
            action, feedback, violations = await self._evaluate_availability(args)
        else:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.UNAUTHORIZED_TOOL,
                    message=f"Function '{fn}' is not authorized by clinic policy.",
                )
            )
            action = GuardrailAction.BLOCK
            feedback = f"Error: Tool '{fn}' is prohibited."

        overhead_ms = round((time.perf_counter() - start_t) * 1000, 2)

        return GuardrailEvaluationResult(
            action=action,
            is_allowed=(action != GuardrailAction.BLOCK),
            function_name=fn,
            arguments=sanitized_args,
            violations=violations,
            feedback_to_agent=feedback,
            overhead_ms=overhead_ms,
        )

    async def _evaluate_cancellation(
        self, args: Dict[str, Any]
    ) -> tuple[GuardrailAction, str, List[PolicyViolation]]:
        """Evaluate deterministic rules for appointment cancellation."""
        violations: List[PolicyViolation] = []
        booking_id = args.get("booking_id")

        if not booking_id:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.MALFORMED_ARGUMENTS,
                    message="Missing 'booking_id' in cancellation request.",
                )
            )
            return GuardrailAction.BLOCK, "Error: booking_id is required to cancel an appointment.", violations

        booking = await self.booking_repo.get_booking(str(booking_id))
        if not booking:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.MALFORMED_ARGUMENTS,
                    message=f"No booking found matching ID '{booking_id}'.",
                )
            )
            return GuardrailAction.BLOCK, f"Error: Booking ID '{booking_id}' does not exist.", violations

        if booking.status == BookingStatus.CANCELLED:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.MALFORMED_ARGUMENTS,
                    message=f"Booking '{booking_id}' has already been cancelled.",
                )
            )
            return GuardrailAction.BLOCK, "Notice: This appointment was already cancelled previously.", violations

        # Rule: Cannot cancel within 2 hours of appointment time
        now = datetime.now(timezone.utc)
        time_diff = booking.slot_time - now
        if time_diff.total_seconds() < 7200 and time_diff.total_seconds() > 0:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.OUTSIDE_BUSINESS_HOURS,
                    message="Late cancellation policy: cannot cancel within 2 hours of appointment without staff assistance.",
                    remedy_suggestion="Please connect customer to a human receptionist.",
                )
            )
            return (
                GuardrailAction.BLOCK,
                "Policy Breach: Cancellations within 2 hours of the slot require receptionist assistance.",
                violations,
            )

        # Valid cancellation: apply deterministic update
        await self.booking_repo.cancel_booking(booking_id)
        return GuardrailAction.ALLOW, f"Appointment '{booking_id}' successfully cancelled.", violations

    async def _evaluate_scheduling(
        self, args: Dict[str, Any]
    ) -> tuple[GuardrailAction, str, List[PolicyViolation], Dict[str, Any]]:
        """Evaluate deterministic rules for appointment creation."""
        violations: List[PolicyViolation] = []
        sanitized = dict(args)

        name = args.get("customer_name")
        phone = args.get("customer_phone", "")
        slot_str = args.get("slot_time")
        service_str = args.get("service_type", "consultation").lower()

        if not name or len(str(name).strip()) < 2:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.INVALID_CONTACT_INFO,
                    message="Customer name is required and must have at least 2 characters.",
                )
            )
            return GuardrailAction.BLOCK, "Error: Valid customer name is required.", violations, sanitized

        # Validate phone
        digits = "".join(filter(str.isdigit, str(phone)))
        if len(digits) < 10:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.INVALID_CONTACT_INFO,
                    message="Customer phone number must contain at least 10 digits.",
                )
            )
            return GuardrailAction.BLOCK, "Error: Invalid phone number format.", violations, sanitized

        sanitized["customer_phone"] = digits

        # Parse slot time
        try:
            if isinstance(slot_str, str):
                slot_time = datetime.fromisoformat(slot_str.replace("Z", "+00:00"))
            elif isinstance(slot_str, datetime):
                slot_time = slot_str
            else:
                raise ValueError("Invalid format")
        except Exception:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.MALFORMED_ARGUMENTS,
                    message=f"Invalid date-time format for slot_time: '{slot_str}'.",
                )
            )
            return GuardrailAction.BLOCK, "Error: Invalid slot date/time format.", violations, sanitized

        try:
            service_type = ServiceType(service_str)
        except ValueError:
            service_type = ServiceType.CONSULTATION

        # Deterministic collision check
        is_free = await self.booking_repo.check_slot_available(slot_time, service_type)
        if not is_free:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.SLOT_UNAVAILABLE,
                    message=f"Slot at {slot_time.isoformat()} for {service_type.value} is already booked.",
                    remedy_suggestion="Please check the next hour or alternative date.",
                )
            )
            return (
                GuardrailAction.BLOCK,
                f"Conflict: Slot at {slot_time.strftime('%Y-%m-%d %H:%M UTC')} is already reserved. Please select another slot.",
                violations,
                sanitized,
            )

        # Create confirmed booking
        booking = Booking(
            customer_name=str(name).strip(),
            customer_phone=digits,
            service_type=service_type,
            slot_time=slot_time,
            status=BookingStatus.CONFIRMED,
            notes=args.get("notes"),
        )
        created = await self.booking_repo.create_booking(booking)
        sanitized["booking_id"] = created.id

        return (
            GuardrailAction.ALLOW,
            f"Appointment confirmed! Booking ID: {created.id} for {slot_time.strftime('%Y-%m-%d %H:%M UTC')}.",
            violations,
            sanitized,
        )

    async def _evaluate_availability(
        self, args: Dict[str, Any]
    ) -> tuple[GuardrailAction, str, List[PolicyViolation]]:
        """Evaluate slot availability query."""
        violations: List[PolicyViolation] = []
        slot_str = args.get("slot_time")
        service_str = args.get("service_type", "consultation").lower()

        try:
            if isinstance(slot_str, str):
                slot_time = datetime.fromisoformat(slot_str.replace("Z", "+00:00"))
            elif isinstance(slot_str, datetime):
                slot_time = slot_str
            else:
                raise ValueError("Invalid format")
            service_type = ServiceType(service_str)
        except Exception:
            violations.append(
                PolicyViolation(
                    policy_type=PolicyType.MALFORMED_ARGUMENTS,
                    message=f"Invalid arguments for availability check: {args}",
                )
            )
            return GuardrailAction.BLOCK, "Error: Invalid date or service type.", violations

        is_free = await self.booking_repo.check_slot_available(slot_time, service_type)
        if is_free:
            return GuardrailAction.ALLOW, f"Slot {slot_time.strftime('%Y-%m-%d %H:%M UTC')} is available.", violations
        else:
            return (
                GuardrailAction.ALLOW,
                f"Slot {slot_time.strftime('%Y-%m-%d %H:%M UTC')} is currently occupied. Recommend another time.",
                violations,
            )
