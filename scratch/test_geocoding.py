import os
import uuid
from schemas.models import ProviderCreate, Location, ServiceType
from tools.database_service import db_service

def test_registration():
    print("Testing provider registration with empty lat/lng...")
    
    # 1. Prepare data with missing lat/lng (None)
    payload = {
        "name": "Super Islamabad Plumber",
        "service_type": ServiceType.PLUMBER,
        "rating": 4.8,
        "location": {
            "address": "G-13, Islamabad",
            "lat": None,
            "lng": None
        },
        "phone": "+923005556667",
        "price_per_hour": 1400.0,
        "experience_years": 8,
        "availability": True,
        "range_km": 15.0
    }
    
    body = ProviderCreate(**payload)
    print(f"Parsed Pydantic body successfully: {body}")
    
    # 2. Emulate router logic (geocoding)
    lat = body.location.lat
    lng = body.location.lng
    if lat is None or lng is None or (lat == 0.0 and lng == 0.0):
        from tools.maps_tool import maps_tool
        coords = maps_tool.geocode(body.location.address)
        body.location.lat = coords.get("lat")
        body.location.lng = coords.get("lng")
        
    print(f"Geocoded coords: lat={body.location.lat}, lng={body.location.lng}")
    assert body.location.lat == 33.6844
    assert body.location.lng == 73.0479
    print("✅ Fallback geocoding for Islamabad matches exactly!")

    # 3. Create the Provider domain object
    from schemas.models import Provider
    new_id = f"p-{uuid.uuid4().hex[:8]}"
    provider = Provider(
        id=new_id,
        name=body.name,
        service_type=body.service_type,
        rating=body.rating,
        location=body.location,
        phone=body.phone,
        price_per_hour=body.price_per_hour,
        experience_years=body.experience_years,
        availability=body.availability,
        range_km=body.range_km
    )
    
    # 4. Save using db_service
    saved = db_service.create_provider(provider)
    print(f"Created provider in DB: {saved.id}, name={saved.name}, lat={saved.location.lat}, lng={saved.location.lng}, range_km={saved.range_km}")
    
    # Retrieve from DB to verify range_km and coords
    retrieved = db_service.get_provider_by_id(new_id)
    print(f"Retrieved provider from DB: {retrieved.id}, name={retrieved.name}, lat={retrieved.location.lat}, lng={retrieved.location.lng}, range_km={retrieved.range_km}")
    
    assert retrieved.location.lat == 33.6844
    assert retrieved.location.lng == 73.0479
    assert retrieved.range_km == 15.0
    print("✅ Integration test passed successfully!")

if __name__ == "__main__":
    test_registration()
