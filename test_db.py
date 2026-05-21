from db.mock_db import db
from schemas.models import Booking, Location, ServiceType, BookingStatus
import datetime

b = Booking(
    id="BK-123",
    user_id="U1",
    provider_id="P1",
    service_type=ServiceType.PLUMBER,
    scheduled_at=datetime.datetime.now(),
    location=Location(address="Test", lat=0, lng=0)
)
db.save_booking(b)

print("Initial:")
print(db.get_booking_by_id("BK-123"))

print("\nUpdating status 1:")
print(db.update_booking_status("BK-123", BookingStatus.PROVIDER_ON_THE_WAY))

print("\nUpdating status 2:")
print(db.update_booking_status("BK-123", BookingStatus.ARRIVED))
