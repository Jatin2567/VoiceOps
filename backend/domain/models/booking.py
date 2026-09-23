"""Domain models for booking business entities and operations."""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class BookingStatus(str, Enum):
    """Lifecycle status of a customer booking."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ServiceType(str, Enum):
    """Supported operational service categories."""
    CONSULTATION = "consultation"
    CHECKUP = "checkup"
    CLEANING = "cleaning"
    PROCEDURE = "procedure"
    FOLLOW_UP = "follow_up"
    GENERAL = "general"


class Booking(BaseModel):
    """Core domain entity representing a confirmed or pending appointment."""
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique booking identifier"
    )
    customer_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full name of customer"
    )
    customer_phone: str = Field(
        ...,
        description="E.164 or 10-digit phone number"
    )
    service_type: ServiceType = Field(
        default=ServiceType.CONSULTATION,
        description="Service type requested"
    )
    slot_time: datetime = Field(
        ...,
        description="Scheduled appointment date and time (UTC)"
    )
    status: BookingStatus = Field(
        default=BookingStatus.CONFIRMED,
        description="Booking status"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Special instructions or customer notes"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp"
    )

    @field_validator("customer_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = "".join(filter(lambda c: c.isdigit() or c == "+", v))
        if len(cleaned) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        return cleaned


class BookingCreateRequest(BaseModel):
    """Request payload to create an appointment."""
    customer_name: str = Field(..., min_length=2)
    customer_phone: str = Field(...)
    service_type: ServiceType = Field(default=ServiceType.CONSULTATION)
    slot_time: datetime = Field(...)
    notes: Optional[str] = Field(default=None)


class BookingCancelRequest(BaseModel):
    """Request payload to cancel an existing appointment."""
    booking_id: str = Field(..., description="Target booking identifier")
    reason: Optional[str] = Field(default=None, description="Cancellation reason")


class SlotAvailabilityCheck(BaseModel):
    """Query to check whether a specific time slot is free."""
    slot_time: datetime = Field(...)
    service_type: ServiceType = Field(default=ServiceType.CONSULTATION)
