"""Unit tests for Booking domain models."""
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from backend.domain.models.booking import (
    Booking,
    BookingCancelRequest,
    BookingCreateRequest,
    BookingStatus,
    ServiceType,
    SlotAvailabilityCheck,
)


class TestBookingModels(unittest.TestCase):
    """Test suite for booking domain entities and validations."""

    def test_booking_creation_valid(self):
        """Verify valid booking model creation."""
        now = datetime.now(timezone.utc)
        booking = Booking(
            customer_name="Alice Smith",
            customer_phone="+1 555 123 4567",
            service_type=ServiceType.CHECKUP,
            slot_time=now,
            status=BookingStatus.CONFIRMED,
            notes="First visit"
        )
        self.assertIsNotNone(booking.id)
        self.assertEqual(booking.customer_name, "Alice Smith")
        # Ensure phone validation cleaned phone string
        self.assertEqual(booking.customer_phone, "+15551234567")
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)

    def test_booking_phone_validation_failure(self):
        """Verify phone with fewer than 10 digits raises validation error."""
        now = datetime.now(timezone.utc)
        with self.assertRaises(ValidationError):
            Booking(
                customer_name="Bob Jones",
                customer_phone="12345",  # Invalid short phone
                service_type=ServiceType.CONSULTATION,
                slot_time=now,
            )

    def test_booking_requests(self):
        """Verify booking requests serialize properly."""
        slot = datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc)
        req = BookingCreateRequest(
            customer_name="Charlie Brown",
            customer_phone="5551234567",
            service_type=ServiceType.CLEANING,
            slot_time=slot,
        )
        self.assertEqual(req.customer_name, "Charlie Brown")

        cancel_req = BookingCancelRequest(
            booking_id="bk-101",
            reason="Scheduling conflict"
        )
        self.assertEqual(cancel_req.booking_id, "bk-101")

        check = SlotAvailabilityCheck(
            slot_time=slot,
            service_type=ServiceType.CLEANING
        )
        self.assertEqual(check.slot_time, slot)


if __name__ == "__main__":
    unittest.main()
