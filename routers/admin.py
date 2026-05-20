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
        "location": {"address": p.location.address, "lat": p.location.lat, "lng": p.location.lng},
    }


def _log_to_dict(log):
    return {
        "id": log.id,
        "user_id": log.user_id,
        "raw_query": log.raw_query,
        "urgency": log.urgency,
        "intent": log.intent,
        "language": log.language,
        "status": log.status,
        "booking_id": log.booking_id,
        "trace": log.trace,
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


@router.post("/bookings/{booking_id}/complete")
async def complete_booking(booking_id: str):
    booking = db_service.complete_booking_admin(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    return api_response(success=True, message="Booking completed", data=_booking_to_dict(booking))


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str):
    booking = db_service.cancel_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    return api_response(success=True, message="Booking cancelled", data=_booking_to_dict(booking))


# ── Providers ─────────────────────────────────────────────────────────────────

@router.get("/providers/")
async def get_all_providers():
    data = [_provider_to_dict(p) for p in db_service.get_all_providers()]
    return api_response(success=True, message="Admin providers retrieved", data=data)


@router.post("/providers/")
async def create_provider(body: ProviderCreate):
    import uuid
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
    )
    db_service.create_provider(provider)
    return api_response(success=True, message="Provider created", data=_provider_to_dict(provider))


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderCreate):
    existing = db_service.get_provider_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} not found")
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
