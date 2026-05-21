"""
database_service.py — Data Access Layer between agents/API and the database.

Set  USE_REAL_DB=true  in your .env to activate SQLAlchemy / SQLite.
When USE_REAL_DB is absent or false, the original MockDB is used (default).

The interface is IDENTICAL either way, so no changes are needed in agents or
API routers when switching backends.
"""
import os
from typing import List, Optional

from schemas.models import Booking, ServiceType, Provider, AdminRequestLog


USE_REAL_DB = os.getenv("USE_REAL_DB", "false").lower() == "true"


# ── MockDB backend (default) ──────────────────────────────────────────────────

class MockDatabaseService:
    """Thin wrapper over MockDB — maintains the existing in-memory behaviour."""

    def __init__(self):
        from db.mock_db import db as _mock
        self._db = _mock

    # Provider
    def get_providers_by_type(self, service_type: ServiceType) -> List[Provider]:
        return self._db.get_providers_by_type(service_type)

    def get_provider_by_id(self, provider_id: str) -> Optional[Provider]:
        return self._db.get_provider_by_id(provider_id)

    def get_all_providers(self) -> List[Provider]:
        return list(self._db.providers.values())

    def create_provider(self, provider: Provider) -> Provider:
        return self._db.create_provider(provider)

    def update_provider(self, provider_id: str, provider: Provider) -> Optional[Provider]:
        return self._db.update_provider(provider_id, provider)

    def delete_provider(self, provider_id: str) -> bool:
        return self._db.delete_provider(provider_id)

    def toggle_provider_availability(self, provider_id: str) -> Optional[Provider]:
        return self._db.toggle_provider_availability(provider_id)

    # Booking
    def save_booking(self, booking: Booking) -> Booking:
        return self._db.save_booking(booking)

    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]:
        return self._db.get_booking_by_id(booking_id)

    def get_all_bookings(self) -> List[Booking]:
        return self._db.get_all_bookings()

    def get_bookings_by_user(self, user_id: str) -> List[Booking]:
        return [b for b in self._db.get_all_bookings() if b.user_id == user_id]

    def cancel_booking(self, booking_id: str) -> Optional[Booking]:
        return self._db.cancel_booking(booking_id)

    def complete_booking_admin(self, booking_id: str) -> Optional[Booking]:
        return self._db.complete_booking_admin(booking_id)

    def update_booking_status(self, booking_id: str, new_status) -> Optional[Booking]:
        return self._db.update_booking_status(booking_id, new_status)

    # Admin logs
    def log_request(self, entry: AdminRequestLog) -> None:
        self._db.log_request(entry)

    def get_all_request_logs(self) -> List[AdminRequestLog]:
        return self._db.get_all_request_logs()

    def get_request_log_by_id(self, request_id: str) -> Optional[AdminRequestLog]:
        return self._db.get_request_log_by_id(request_id)

    # FCM Tokens
    def register_fcm_token(self, user_id: str, fcm_token: str, device_id: str = None) -> None:
        self._db.register_fcm_token(user_id, fcm_token, device_id)

    def get_fcm_tokens(self, user_id: str) -> List[str]:
        return self._db.get_fcm_tokens(user_id)

    def remove_fcm_token(self, fcm_token: str) -> None:
        self._db.remove_fcm_token(fcm_token)


# ── SQLAlchemy backend ────────────────────────────────────────────────────────

class SQLDatabaseService:
    """
    Wraps domain repositories with per-call session management.
    Each method opens a fresh session so this can be used
    safely from FastAPI background tasks and LangGraph nodes.
    """

    def __init__(self):
        from db.database import SessionLocal
        self._SessionLocal = SessionLocal

    # Provider
    def get_providers_by_type(self, service_type: ServiceType) -> List[Provider]:
        with self._session_scope() as scope:
            return scope.providers.get_providers_by_type(service_type)

    def get_provider_by_id(self, provider_id: str) -> Optional[Provider]:
        with self._session_scope() as scope:
            return scope.providers.get_provider_by_id(provider_id)

    def get_all_providers(self) -> List[Provider]:
        with self._session_scope() as scope:
            return scope.providers.get_all_providers()

    def create_provider(self, provider: Provider) -> Provider:
        with self._session_scope() as scope:
            return scope.providers.create_provider(provider)

    def update_provider(self, provider_id: str, provider: Provider) -> Optional[Provider]:
        with self._session_scope() as scope:
            existing = scope.providers.get_provider_by_id(provider_id)
            if not existing:
                return None
            provider.id = provider_id
            return scope.providers.create_provider(provider)

    def delete_provider(self, provider_id: str) -> bool:
        with self._session_scope() as scope:
            return scope.providers.delete_provider(provider_id)

    def toggle_provider_availability(self, provider_id: str) -> Optional[Provider]:
        with self._session_scope() as scope:
            return scope.providers.toggle_provider_availability(provider_id)

    # Booking
    def save_booking(self, booking: Booking) -> Booking:
        with self._session_scope() as scope:
            return scope.bookings.save_booking(booking)

    def get_booking_by_id(self, booking_id: str) -> Optional[Booking]:
        with self._session_scope() as scope:
            return scope.bookings.get_booking_by_id(booking_id)

    def get_all_bookings(self) -> List[Booking]:
        with self._session_scope() as scope:
            return scope.bookings.get_all_bookings()

    def get_bookings_by_user(self, user_id: str) -> List[Booking]:
        with self._session_scope() as scope:
            return scope.bookings.get_bookings_by_user(user_id)

    def cancel_booking(self, booking_id: str) -> Optional[Booking]:
        with self._session_scope() as scope:
            return scope.bookings.cancel_booking(booking_id)

    def complete_booking_admin(self, booking_id: str) -> Optional[Booking]:
        with self._session_scope() as scope:
            return scope.bookings.complete_booking_admin(booking_id)

    def update_booking_status(self, booking_id: str, new_status) -> Optional[Booking]:
        with self._session_scope() as scope:
            # Note: This is a placeholder. A full SQL implementation would update the booking.
            # We'll use the MockDB for the hackathon context.
            booking = scope.bookings.get_booking_by_id(booking_id)
            if booking:
                booking.status = new_status
                return scope.bookings.save_booking(booking)
            return None

    # Admin logs
    def log_request(self, entry: AdminRequestLog) -> None:
        with self._session_scope() as scope:
            scope.logs.log_request(entry)

    def get_all_request_logs(self) -> List[AdminRequestLog]:
        with self._session_scope() as scope:
            return scope.logs.get_all_request_logs()

    def get_request_log_by_id(self, request_id: str) -> Optional[AdminRequestLog]:
        with self._session_scope() as scope:
            return scope.logs.get_request_log_by_id(request_id)

    # FCM Tokens
    def register_fcm_token(self, user_id: str, fcm_token: str, device_id: str = None) -> None:
        with self._session_scope() as scope:
            from db.models import FCMToken
            # Remove existing token for same device
            if device_id:
                scope._session.query(FCMToken).filter(
                    FCMToken.user_id == user_id,
                    FCMToken.device_id == device_id
                ).delete()
            
            # Remove existing entry if token already exists somewhere
            scope._session.query(FCMToken).filter(FCMToken.fcm_token == fcm_token).delete()
            
            new_token = FCMToken(user_id=user_id, fcm_token=fcm_token, device_id=device_id)
            scope._session.add(new_token)
            try:
                scope._session.commit()
            except Exception:
                scope._session.rollback()

    def get_fcm_tokens(self, user_id: str) -> List[str]:
        with self._session_scope() as scope:
            from db.models import FCMToken
            tokens = scope._session.query(FCMToken).filter(FCMToken.user_id == user_id).all()
            return [t.fcm_token for t in tokens]

    def remove_fcm_token(self, fcm_token: str) -> None:
        with self._session_scope() as scope:
            from db.models import FCMToken
            scope._session.query(FCMToken).filter(FCMToken.fcm_token == fcm_token).delete()
            try:
                scope._session.commit()
            except Exception:
                scope._session.rollback()

    # Context manager — opens and closes a DB session cleanly
    class _session_scope:
        def __init__(self):
            from db.database import SessionLocal
            from db.repositories.provider_repository import ProviderRepository
            from db.repositories.booking_repository import BookingRepository
            from db.repositories.log_repository import LogRepository
            self._session = SessionLocal()
            self.providers = ProviderRepository(self._session)
            self.bookings = BookingRepository(self._session)
            self.logs = LogRepository(self._session)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self._session.close()


# ── Factory: pick the right backend ──────────────────────────────────────────

if USE_REAL_DB:
    db_service = SQLDatabaseService()
    print("[database_service] Using SQLAlchemy SQL backend.")
else:
    db_service = MockDatabaseService()
    print("[database_service] Using MockDB backend (development).")

