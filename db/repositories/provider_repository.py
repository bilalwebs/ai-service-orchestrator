from typing import List, Optional
from sqlalchemy.orm import Session

from schemas.models import (
    Provider as ProviderSchema,
    Location,
    ServiceType,
)
from db import models

class ProviderRepository:
    """Domain repository for Provider entities."""

    def __init__(self, session: Session):
        self._db = session

    def get_providers_by_type(self, service_type: ServiceType) -> List[ProviderSchema]:
        rows = (
            self._db.query(models.Provider)
            .filter(models.Provider.service_type == service_type)
            .all()
        )
        return [self._orm_to_provider(r) for r in rows]

    def get_provider_by_id(self, provider_id: str) -> Optional[ProviderSchema]:
        row = self._db.get(models.Provider, provider_id)
        return self._orm_to_provider(row) if row else None

    def get_all_providers(self) -> List[ProviderSchema]:
        rows = self._db.query(models.Provider).all()
        return [self._orm_to_provider(r) for r in rows]

    def create_provider(self, provider: ProviderSchema) -> ProviderSchema:
        row = models.Provider(
            id=provider.id,
            name=provider.name,
            service_type=provider.service_type,
            rating=provider.rating,
            address=provider.location.address,
            lat=provider.location.lat,
            lng=provider.location.lng,
            phone=provider.phone,
            price_per_hour=provider.price_per_hour,
            experience_years=provider.experience_years,
            availability=provider.availability,
        )
        try:
            self._db.add(row)
            self._db.commit()
            self._db.refresh(row)
        except Exception:
            self._db.rollback()
            raise
        return self._orm_to_provider(row)

    def toggle_provider_availability(self, provider_id: str) -> Optional[ProviderSchema]:
        row = self._db.get(models.Provider, provider_id)
        if not row:
            return None
        try:
            row.availability = not row.availability
            self._db.commit()
            self._db.refresh(row)
        except Exception:
            self._db.rollback()
            raise
        return self._orm_to_provider(row)

    def delete_provider(self, provider_id: str) -> bool:
        row = self._db.get(models.Provider, provider_id)
        if not row:
            return False
        try:
            self._db.delete(row)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return True

    @staticmethod
    def _orm_to_provider(row: models.Provider) -> ProviderSchema:
        return ProviderSchema(
            id=row.id,
            name=row.name,
            service_type=row.service_type,
            rating=row.rating,
            location=Location(address=row.address, lat=row.lat, lng=row.lng),
            phone=row.phone,
            price_per_hour=row.price_per_hour,
            experience_years=row.experience_years,
            availability=row.availability,
        )
