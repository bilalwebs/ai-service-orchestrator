from typing import List, Optional
from sqlalchemy.orm import Session

from schemas.models import (
    Booking as BookingSchema,
    BookingStatus,
    Location,
)
from db import models

class BookingRepository:
    """Domain repository for Booking entities."""

    def __init__(self, session: Session):
        self._db = session

    def save_booking(self, booking: BookingSchema) -> BookingSchema:
        existing = self._db.get(models.Booking, booking.id)
        try:
            if existing:
                existing.status = booking.status
                existing.updated_at = booking.updated_at
                self._db.commit()
                self._db.refresh(existing)
                return self._orm_to_booking(existing)

            row = models.Booking(
                id=booking.id,
                user_id=booking.user_id,
                provider_id=booking.provider_id,
                service_type=booking.service_type,
                status=booking.status,
                scheduled_at=booking.scheduled_at,
                address=booking.location.address,
                lat=booking.location.lat,
                lng=booking.location.lng,
                total_cost=booking.total_cost,
                created_at=booking.created_at,
                updated_at=booking.updated_at,
            )
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
        except Exception:
            self._db.rollback()
            raise
        return self._orm_to_booking(row)

    def get_booking_by_id(self, booking_id: str) -> Optional[BookingSchema]:
        row = self._db.get(models.Booking, booking_id)
        return self._orm_to_booking(row) if row else None

    def get_all_bookings(self) -> List[BookingSchema]:
        rows = self._db.query(models.Booking).all()
        return [self._orm_to_booking(r) for r in rows]

    def get_bookings_by_user(self, user_id: str) -> List[BookingSchema]:
        rows = (
            self._db.query(models.Booking)
            .filter(models.Booking.user_id == user_id)
            .all()
        )
        return [self._orm_to_booking(r) for r in rows]

    def cancel_booking(self, booking_id: str) -> Optional[BookingSchema]:
        row = self._db.get(models.Booking, booking_id)
        if not row:
            return None
        try:
            row.status = BookingStatus.CANCELLED
            self._db.commit()
            self._db.refresh(row)
        except Exception:
            self._db.rollback()
            raise
        return self._orm_to_booking(row)

    def complete_booking_admin(self, booking_id: str) -> Optional[BookingSchema]:
        row = self._db.get(models.Booking, booking_id)
        if not row:
            return None
        try:
            row.status = BookingStatus.COMPLETED
            self._db.commit()
            self._db.refresh(row)
        except Exception:
            self._db.rollback()
            raise
        return self._orm_to_booking(row)

    @staticmethod
    def _orm_to_booking(row: models.Booking) -> BookingSchema:
        return BookingSchema(
            id=row.id,
            user_id=row.user_id,
            provider_id=row.provider_id,
            service_type=row.service_type,
            status=row.status,
            scheduled_at=row.scheduled_at,
            location=Location(address=row.address, lat=row.lat, lng=row.lng),
            total_cost=row.total_cost,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
