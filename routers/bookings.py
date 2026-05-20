import asyncio
from fastapi import APIRouter, HTTPException
from tools.database_service import db_service
from agents.graph import complete_booking_node
from utils.request_id import generate_request_id
from logs.logger import log_interaction
from schemas.response import api_response

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.get("/user/{user_id}")
async def get_booking_history(user_id: str):
    """Retrieve past and upcoming bookings for a specific user."""
    user_bookings = db_service.get_bookings_by_user(user_id)
    return api_response(success=True, message="User bookings retrieved successfully", data=user_bookings)


@router.get("/detail/{booking_id}")
async def get_booking_detail(booking_id: str):
    """Get the status and details of a specific booking."""
    booking = db_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return api_response(success=True, message="Booking details retrieved successfully", data=booking)


@router.post("/{booking_id}/cancel")
async def cancel_booking(booking_id: str):
    """Update the booking status to CANCELLED."""
    booking = db_service.cancel_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return api_response(success=True, message=f"Booking {booking_id} cancelled successfully", data=booking)


# FIX 4: Canonical booking completion endpoint — moved from /requests router
@router.post("/{booking_id}/complete")
async def complete_booking(booking_id: str):
    """Mark a booking as completed (canonical endpoint)."""
    request_id = generate_request_id()

    log_interaction(
        request_id=request_id,
        stage="booking_completion_requested",
        message=f"Booking {booking_id} completion requested",
        status="success",
    )

    booking = db_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")

    initial_state = {
        "booking":    booking,
        "trace":      [],
        "request_id": request_id,
    }

    try:
        result = await complete_booking_node(initial_state)
        log_interaction(
            request_id=request_id,
            stage="booking_completed",
            message=f"Booking {booking_id} marked as completed",
            status="success",
        )
    except Exception as e:
        log_interaction(
            request_id=request_id,
            stage="booking_completion_failed",
            message=f"Completion failed: {str(e)}",
            status="error",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Booking completion failed: {str(e)}")

    return api_response(
        success=True,
        message=f"Booking {booking_id} marked as completed.",
        data={"trace": result.get("trace", [])}
    )
