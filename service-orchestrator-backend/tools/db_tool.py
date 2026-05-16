from schemas.models import Booking, ServiceType, Provider
from typing import List

# Import from your MockDB file
from db.mock_db import db   # ← Adjust path if your folder structure is different


class DBTool:
    def get_providers_by_type(self, service_type: ServiceType) -> List[Provider]:
        """Get providers by service type"""
        return db.get_providers_by_type(service_type)

    def save_booking(self, booking: Booking):
        """Save booking - Used in graph.py"""
        return db.save_booking(booking)

    def get_provider_by_id(self, provider_id: str) -> Provider | None:
        """Optional: Get single provider by ID"""
        return db.providers.get(provider_id)

    def get_all_bookings(self):
        """Optional: For debugging"""
        return db.get_all_bookings()


# Global instance
db_tool = DBTool()