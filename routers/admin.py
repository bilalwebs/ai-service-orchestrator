from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException
from tools.database_service import db_service
from schemas.models import Provider, ServiceType, Location, ProviderCreate
from utils.request_id import generate_request_id
from schemas.response import api_response

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Helpers ─────────────────────────────────────────────────────────────────

def _booking_to_dict(b):
    return {
        "id": b.id,
        "user_id": b.user_id,
        "provider_id": b.provider_id,
        "service_type": b.service_type.value if hasattr(b.service_type, "value") else b.service_type,
        "status": b.status.value if hasattr(b.status, "value") else b.status,
        "scheduled_at": b.scheduled_at.isoformat() if hasattr(b.scheduled_at, "isoformat") else str(b.scheduled_at),
        "location": {"address": b.location.address, "lat": b.location.lat, "lng": b.location.lng},
        "total_cost": b.total_cost,
        "created_at": b.created_at.isoformat() if hasattr(b.created_at, "isoformat") else str(b.created_at),
    }


def _provider_to_dict(p):
    return {
        "id": p.id,
        "name": p.name,
        "service_type": p.service_type.value if hasattr(p.service_type, "value") else p.service_type,
        "rating": p.rating,
        "phone": p.phone,
        "price_per_hour": p.price_per_hour,
        "experience_years": p.experience_years,
        "availability": p.availability,
        "range_km": getattr(p, "range_km", 10.0),
        "location": {"address": p.location.address, "lat": p.location.lat, "lng": p.location.lng},
    }


def _normalize_trace_item(t: dict) -> dict:
    """Normalize trace items for clients.
    Old DB entries used step_name/description; current entries use stage/message."""
    return {
        "stage":   t.get("stage")   or t.get("step_name") or "unknown",
        "message": t.get("message") or t.get("description") or "",
        "status":  t.get("status")  or "unknown",
    }


def _log_to_dict(log):
    raw_trace = log.trace if isinstance(log.trace, list) else []
    return {
        "id": log.id,
        "user_id": log.user_id,
        "raw_query": log.raw_query,
        "urgency": log.urgency,
        "intent": log.intent,
        "language": log.language,
        "status": log.status,
        "booking_id": log.booking_id,
        "trace": [_normalize_trace_item(t) for t in raw_trace if isinstance(t, dict)],
        "created_at": log.created_at,
    }


# ── Bookings ─────────────────────────────────────────────────────────────────

@router.get("/bookings/")
async def get_all_bookings():
    data = [_booking_to_dict(b) for b in db_service.get_all_bookings()]
    return api_response(success=True, message="Admin bookings retrieved", data=data)


@router.get("/bookings/{booking_id}")
async def get_booking(booking_id: str):
    booking = db_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    return api_response(success=True, message="Admin booking retrieved", data=_booking_to_dict(booking))


async def _handle_status_change_notification(booking, new_status: str):
    """Helper to generate AI follow-ups and send FCM push notification."""
    try:
        from tools.notification_service import notify_user
        from agents.followup_ai import generate_followup_actions
        
        provider = db_service.get_provider_by_id(booking.provider_id)
        
        # Determine language (try to get from request log, default to en)
        # Note: In a real system, you'd store language on the user or booking.
        language = "en"
        logs = db_service.get_all_request_logs()
        for log in logs:
            if log.booking_id == booking.id:
                language = log.language
                break
                
        # Generate AI follow-up actions
        ai_data = await generate_followup_actions(booking, new_status, provider, language)
        
        # Send push notification
        title = f"Booking {new_status.title()}"
        body = f"Your {booking.service_type.value.replace('_', ' ')} booking is now {new_status}."
        if new_status == "completed":
            body = f"Service completed! Tap to see next steps."
        elif new_status == "cancelled":
            body = f"Your booking has been cancelled."
            
        notify_user(booking.user_id, title, body, data=ai_data)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send status change notification: {e}")


@router.post("/bookings/{booking_id}/complete")
async def complete_booking(booking_id: str):
    booking = db_service.complete_booking_admin(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
        
    await _handle_status_change_notification(booking, "completed")
    return api_response(success=True, message="Booking completed", data=_booking_to_dict(booking))


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str):
    booking = db_service.cancel_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
        
    await _handle_status_change_notification(booking, "cancelled")
    return api_response(success=True, message="Booking cancelled", data=_booking_to_dict(booking))


@router.patch("/bookings/{booking_id}/status")
async def update_booking_status(booking_id: str, payload: dict):
    from schemas.models import BookingStatus
    
    new_status_str = payload.get("status")
    if not new_status_str:
        raise HTTPException(status_code=422, detail="Status field is required")
        
    try:
        new_status = BookingStatus(new_status_str)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {new_status_str}")
        
    booking = db_service.update_booking_status(booking_id, new_status)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
        
    await _handle_status_change_notification(booking, new_status.value)
    return api_response(success=True, message=f"Booking status updated to {new_status.value}", data=_booking_to_dict(booking))

# ── Providers ─────────────────────────────────────────────────────────────────

@router.get("/providers/")
async def get_all_providers():
    data = [_provider_to_dict(p) for p in db_service.get_all_providers()]
    return api_response(success=True, message="Admin providers retrieved", data=data)


@router.post("/providers/")
async def create_provider(body: ProviderCreate):
    import uuid
    new_id = f"p-{uuid.uuid4().hex[:8]}"
    
    # Geocode if lat/lng are missing/0.0
    lat = body.location.lat
    lng = body.location.lng
    if lat is None or lng is None or (lat == 0.0 and lng == 0.0):
        from tools.maps_tool import maps_tool
        coords = maps_tool.geocode(body.location.address)
        body.location.lat = coords.get("lat", 24.8607)
        body.location.lng = coords.get("lng", 67.0011)

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
        range_km=body.range_km,
    )
    db_service.create_provider(provider)
    return api_response(success=True, message="Provider created", data=_provider_to_dict(provider))


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderCreate):
    existing = db_service.get_provider_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    
    # Geocode if lat/lng are missing/0.0
    lat = body.location.lat
    lng = body.location.lng
    if lat is None or lng is None or (lat == 0.0 and lng == 0.0):
        from tools.maps_tool import maps_tool
        coords = maps_tool.geocode(body.location.address)
        body.location.lat = coords.get("lat", 24.8607)
        body.location.lng = coords.get("lng", 67.0011)

    updated = Provider(
        id=provider_id,
        name=body.name,
        service_type=body.service_type,
        rating=body.rating,
        location=body.location,
        phone=body.phone,
        price_per_hour=body.price_per_hour,
        experience_years=body.experience_years,
        availability=body.availability,
        range_km=body.range_km,
    )
    db_service.update_provider(provider_id, updated)
    return api_response(success=True, message="Provider updated", data=_provider_to_dict(updated))


@router.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str):
    success = db_service.delete_provider(provider_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return api_response(success=True, message=f"Provider {provider_id} deleted")


@router.patch("/providers/{provider_id}/availability")
async def toggle_availability(provider_id: str):
    provider = db_service.toggle_provider_availability(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
    return api_response(success=True, message="Provider availability toggled", data=_provider_to_dict(provider))


# ── Requests ─────────────────────────────────────────────────────────────────

@router.get("/requests/")
async def get_all_requests():
    data = [_log_to_dict(log) for log in db_service.get_all_request_logs()]
    return api_response(success=True, message="Admin requests retrieved", data=data)


@router.get("/requests/{request_id}")
async def get_request(request_id: str):
    log = db_service.get_request_log_by_id(request_id)
    if not log:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    return api_response(success=True, message="Admin request log retrieved", data=_log_to_dict(log))
