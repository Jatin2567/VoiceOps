"""Unit tests for MockBookingRepository adapter."""
import unittest
from datetime import datetime, timezone

from backend.domain.models.booking import Booking, BookingStatus, ServiceType
from backend.domain.ports.booking_repository import IBookingRepository
from backend.infrastructure.persistence.mock_booking_repo import MockBookingRepository


class TestMockBookingRepository(unittest.IsolatedAsyncioTestCase):
    """Test suite ensuring MockBookingRepository adheres to IBookingRepository contract."""

    async def asyncSetUp(self):
        self.repo: IBookingRepository = MockBookingRepository(seed_sample_data=True)

    def test_implements_interface(self):
        """Verify MockBookingRepository implements IBookingRepository."""
        self.assertIsInstance(self.repo, IBookingRepository)

    async def test_get_seeded_booking(self):
        """Verify seeded booking retrieval."""
        b = await self.repo.get_booking("book-001")
        self.assertIsNotNone(b)
        self.assertEqual(b.customer_name, "John Doe")
        self.assertEqual(b.status, BookingStatus.CONFIRMED)

    async def test_check_slot_available(self):
        """Verify slot collision detection against seeded bookings."""
        # book-001 is on 2026-09-25 at 10:00 for CONSULTATION
        occupied_slot = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
        free_slot = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)

        is_free_occupied = await self.repo.check_slot_available(
            occupied_slot, ServiceType.CONSULTATION
        )
        self.assertFalse(is_free_occupied)

        is_free_avail = await self.repo.check_slot_available(
            free_slot, ServiceType.CONSULTATION
        )
        self.assertTrue(is_free_avail)

    async def test_create_and_cancel_booking(self):
        """Verify booking creation and subsequent cancellation."""
        new_booking = Booking(
            customer_name="Test Customer",
            customer_phone="+15550001111",
            service_type=ServiceType.GENERAL,
            slot_time=datetime(2026, 9, 26, 9, 0, tzinfo=timezone.utc),
            status=BookingStatus.CONFIRMED
        )
        created = await self.repo.create_booking(new_booking)
        self.assertIsNotNone(created.id)

        # Cancel
        cancelled = await self.repo.cancel_booking(created.id)
        self.assertTrue(cancelled)

        # Verify status updated
        refreshed = await self.repo.get_booking(created.id)
        self.assertIsNotNone(refreshed)
        self.assertEqual(refreshed.status, BookingStatus.CANCELLED)

        # Slot is now available again
        is_free_now = await self.repo.check_slot_available(
            new_booking.slot_time, ServiceType.GENERAL
        )
        self.assertTrue(is_free_now)


if __name__ == "__main__":
    unittest.main()
