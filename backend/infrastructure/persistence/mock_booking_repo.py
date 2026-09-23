"""In-memory booking repository driven adapter."""
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from backend.domain.models.booking import Booking, BookingStatus, ServiceType
from backend.domain.ports.booking_repository import IBookingRepository


class MockBookingRepository(IBookingRepository):
    """
    In-memory thread-safe implementation of IBookingRepository for local development,
    unit testing, and deterministic guardrail validation.
    """

    def __init__(self, seed_sample_data: bool = True):
        self._lock = asyncio.Lock()
        self._storage: Dict[str, Booking] = {}
        if seed_sample_data:
            self._seed_default_bookings()

    def _seed_default_bookings(self) -> None:
        """Seed initial bookings to test slot conflicts and cancellations."""
        seed_id_1 = "book-001"
        self._storage[seed_id_1] = Booking(
            id=seed_id_1,
            customer_name="John Doe",
            customer_phone="+15551234567",
            service_type=ServiceType.CONSULTATION,
            slot_time=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
            status=BookingStatus.CONFIRMED,
            notes="Initial consultation"
        )
        seed_id_2 = "book-002"
        self._storage[seed_id_2] = Booking(
            id=seed_id_2,
            customer_name="Jane Smith",
            customer_phone="+15559876543",
            service_type=ServiceType.CLEANING,
            slot_time=datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc),
            status=BookingStatus.CONFIRMED,
            notes="Regular cleaning"
        )

    async def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Retrieve booking by ID."""
        async with self._lock:
            booking = self._storage.get(booking_id)
            return booking.model_copy() if booking else None

    async def create_booking(self, booking: Booking) -> Booking:
        """Create and store new booking."""
        async with self._lock:
            # Ensure unique ID if not present
            if not booking.id:
                booking = booking.model_copy(update={"id": str(uuid4())})
            self._storage[booking.id] = booking.model_copy()
            return booking.model_copy()

    async def cancel_booking(self, booking_id: str) -> bool:
        """Cancel a booking by setting status to CANCELLED."""
        async with self._lock:
            booking = self._storage.get(booking_id)
            if not booking:
                return False
            self._storage[booking_id] = booking.model_copy(
                update={"status": BookingStatus.CANCELLED}
            )
            return True

    async def check_slot_available(self, slot_time: datetime, service_type: ServiceType) -> bool:
        """
        Check if slot is available.
        A slot is occupied if an active (CONFIRMED/PENDING) booking exists at that exact hour/time.
        """
        async with self._lock:
            for booking in self._storage.values():
                if booking.status in (BookingStatus.CONFIRMED, BookingStatus.PENDING):
                    if booking.slot_time == slot_time and booking.service_type == service_type:
                        return False
            return True

    async def list_bookings(self, status: Optional[BookingStatus] = None) -> List[Booking]:
        """List bookings, optionally filtered by status."""
        async with self._lock:
            if status is None:
                return [b.model_copy() for b in self._storage.values()]
            return [b.model_copy() for b in self._storage.values() if b.status == status]
