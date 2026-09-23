"""Domain port defining the repository contract for booking persistence."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from backend.domain.models.booking import Booking, BookingStatus, ServiceType


class IBookingRepository(ABC):
    """Abstract port for booking storage and lookup (driven adapter interface)."""

    @abstractmethod
    async def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Retrieve a booking by its unique identifier."""
        raise NotImplementedError

    @abstractmethod
    async def create_booking(self, booking: Booking) -> Booking:
        """Persist a new booking entity."""
        raise NotImplementedError

    @abstractmethod
    async def cancel_booking(self, booking_id: str) -> bool:
        """Mark an existing booking as cancelled. Returns True if cancelled, False if not found."""
        raise NotImplementedError

    @abstractmethod
    async def check_slot_available(self, slot_time: datetime, service_type: ServiceType) -> bool:
        """Check whether a specific appointment slot is unreserved."""
        raise NotImplementedError

    @abstractmethod
    async def list_bookings(self, status: Optional[BookingStatus] = None) -> List[Booking]:
        """List all bookings, optionally filtered by status."""
        raise NotImplementedError
