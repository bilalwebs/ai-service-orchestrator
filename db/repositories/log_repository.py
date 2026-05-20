from typing import List, Optional
from sqlalchemy.orm import Session

from schemas.models import (
    AdminRequestLog as AdminRequestLogSchema,
)
from db import models

class LogRepository:
    """Domain repository for AdminRequestLog entities."""

    def __init__(self, session: Session):
        self._db = session

    def log_request(self, entry: AdminRequestLogSchema) -> None:
        existing = self._db.get(models.AdminRequestLog, entry.id)
        if existing:
            existing.user_id = entry.user_id
            existing.raw_query = entry.raw_query
            existing.urgency = entry.urgency
            existing.intent = entry.intent
            existing.language = entry.language
            existing.status = entry.status
            existing.booking_id = entry.booking_id
            existing.trace = entry.trace
        else:
            row = models.AdminRequestLog(
                id=entry.id,
                user_id=entry.user_id,
                raw_query=entry.raw_query,
                urgency=entry.urgency,
                intent=entry.intent,
                language=entry.language,
                status=entry.status,
                booking_id=entry.booking_id,
                trace=entry.trace,
                created_at=entry.created_at,
            )
            self._db.add(row)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

    def get_all_request_logs(self) -> List[AdminRequestLogSchema]:
        rows = self._db.query(models.AdminRequestLog).all()
        return [self._orm_to_log(r) for r in rows]

    def get_request_log_by_id(self, request_id: str) -> Optional[AdminRequestLogSchema]:
        row = self._db.get(models.AdminRequestLog, request_id)
        return self._orm_to_log(row) if row else None

    @staticmethod
    def _orm_to_log(row: models.AdminRequestLog) -> AdminRequestLogSchema:
        return AdminRequestLogSchema(
            id=row.id,
            user_id=row.user_id,
            raw_query=row.raw_query,
            urgency=row.urgency,
            intent=row.intent,
            language=row.language,
            status=row.status,
            booking_id=row.booking_id,
            trace=row.trace or [],
            created_at=row.created_at,
        )
