import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from schemas.models import ServiceRequest, AdminRequestLog
from agents.graph import app_graph, complete_booking_node, _make_trace
from tools.database_service import db_service
from utils.request_id import generate_request_id
from logs.logger import log_interaction
from schemas.response import api_response

router = APIRouter(prefix="/requests", tags=["Service Requests"])

# Timeout (seconds) for the full LangGraph workflow. Guards against LLM hangs.
WORKFLOW_TIMEOUT_SECONDS = int(__import__("os").getenv("WORKFLOW_TIMEOUT_SECONDS", "60"))


@router.post("/")
async def create_service_request(request: ServiceRequest):
    """Main endpoint — runs the full LangGraph agentic workflow."""
    request_id = generate_request_id()

    start_user_input = _make_trace(
        step_name="user_input_received",
        agent_name="router",
        description="Received service request",
        input_data={
            "raw_query": request.raw_query,
            "user_id":   request.user_id,
            "location":  request.location.model_dump() if request.location else None,
        },
        output_data=None,
        reasoning="",
        tool_used="API",
        status="started",
        request_id=request_id,
    )

    log_interaction(
        request_id=request_id,
        stage="request_received",
        message=f"Received: {request.raw_query}",
        status="success",
        user_id=request.user_id,
        raw_query=request.raw_query,
        urgency=request.urgency.value,
        location=request.location.model_dump() if request.location else None,
    )

    end_user_input = _make_trace(
        step_name="user_input_received",
        agent_name="router",
        description="Service request logged",
        input_data={"raw_query": request.raw_query},
        output_data={"status": "logged"},
        reasoning="",
        tool_used="API",
        status="completed",
        request_id=request_id,
    )

    initial_state = {
        "request":           request,
        "intent":            None,
        "language":          request.language_detected or "en",
        "urgency":           request.urgency.value,
        "providers":         [],
        "top_providers":     [],
        "selected_provider": None,
        "booking":           None,
        "trace":             [start_user_input, end_user_input],
        "reasoning":         "",
        "final_response":    None,
        "request_id":        request_id,
    }

    try:
        # FIX 3: Timeout guard — prevents indefinite hang on LLM / network failure
        result = await asyncio.wait_for(
            app_graph.ainvoke(initial_state),
            timeout=WORKFLOW_TIMEOUT_SECONDS,
        )
        log_interaction(
            request_id=request_id,
            stage="workflow_completed",
            message="LangGraph workflow completed successfully",
            status="success",
            booking_id=result.get("booking").id if result.get("booking") else None,
            intent=result.get("intent").value if result.get("intent") else None,
        )
    except asyncio.TimeoutError:
        log_interaction(
            request_id=request_id,
            stage="workflow_timeout",
            message=f"Workflow timed out after {WORKFLOW_TIMEOUT_SECONDS}s",
            status="error",
        )
        raise HTTPException(
            status_code=504,
            detail=f"Workflow timed out after {WORKFLOW_TIMEOUT_SECONDS} seconds. Please try again.",
        )
    except Exception as e:
        log_interaction(
            request_id=request_id,
            stage="workflow_failed",
            message=f"Workflow failed: {str(e)}",
            status="error",
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")

    fo      = result.get("final_response") or {}
    booking = result.get("booking")
    status  = fo.get("status", "error")

    # Build structured next_steps for frontend
    structured_steps = [
        {
            "step":         s.get("step_number", 0),
            "title":        s.get("title", ""),
            "description":  s.get("description", ""),
            "type":         _map_action_type(s.get("action_type", "info")),
            "action_value": s.get("action_value"),
            "action_label": s.get("action_label"),
        }
        for s in fo.get("next_steps", [])
    ]

    # Log the completed request for admin inspection (goes through db_service → mock or SQL)
    db_service.log_request(AdminRequestLog(
        id=request_id,
        user_id=request.user_id,
        raw_query=request.raw_query,
        urgency=request.urgency.value,
        intent=result.get("intent").value if result.get("intent") else None,
        language=result.get("language", "en"),
        status=status,
        booking_id=booking.id if booking else None,
        trace=[t if isinstance(t, dict) else t for t in result.get("trace", [])],
        created_at=datetime.now().isoformat()
    ))

    data_payload = {
        "status":          status,
        "service_request": fo.get("service_request", {}),
        "provider":        fo.get("provider"),
        "appointment":     fo.get("appointment"),
        "top_providers":   fo.get("top_providers"),
        "next_steps":      structured_steps,
        "followup":        fo.get("followup", {}),
        "error":           fo.get("error"),
        "trace":           result.get("trace", []),
        "meta": {
            "booking_id":        booking.id if booking else None,
            "detected_intent":   result.get("intent").value if result.get("intent") else None,
            "detected_language": result.get("language"),
            "urgency":           result.get("urgency"),
            "request_id":        request_id,
        }
    }
    
    return api_response(
        success=(status == "success"),
        message=_build_message(fo, status),
        data=data_payload
    )


def custom_json_serializer(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


@router.post("/stream")
async def create_service_request_stream(request: ServiceRequest):
    """Streaming endpoint — streams LangGraph intermediate events via SSE."""
    request_id = generate_request_id()

    start_user_input = _make_trace(
        step_name="user_input_received", agent_name="router",
        description="Received service request",
        input_data={"raw_query": request.raw_query, "user_id": request.user_id,
                    "location": request.location.model_dump() if request.location else None},
        output_data=None, reasoning="", tool_used="API", status="started", request_id=request_id
    )
    end_user_input = _make_trace(
        step_name="user_input_received", agent_name="router",
        description="Service request logged",
        input_data={"raw_query": request.raw_query}, output_data={"status": "logged"},
        reasoning="", tool_used="API", status="completed", request_id=request_id
    )

    initial_state = {
        "request": request, "intent": None, "language": request.language_detected or "en",
        "urgency": request.urgency.value, "providers": [], "top_providers": [],
        "selected_provider": None, "booking": None,
        "trace": [start_user_input, end_user_input], "reasoning": "",
        "final_response": None, "request_id": request_id,
    }

    # FIX 6: Streaming safety — yield typed events, always send [DONE] sentinel,
    # apply per-chunk timeout so a stalled node does not hang the connection.
    async def event_stream():
        try:
            async for event in app_graph.astream(initial_state, stream_mode="updates"):
                payload = json.dumps(event, default=custom_json_serializer)
                yield f"data: {payload}\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'event': 'error', 'detail': 'Stream timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'detail': str(e)})}\n\n"
        finally:
            # Always send SSE termination sentinel so the client can close cleanly
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable nginx buffering for SSE
            "Connection": "keep-alive",
        },
    )


# FIX 4: Deprecated path — kept for backward compatibility, delegates to bookings router logic
@router.post(
    "/bookings/{booking_id}/complete",
    deprecated=True,
    summary="[Deprecated] Use POST /bookings/{booking_id}/complete instead",
)
async def complete_booking_legacy(booking_id: str):
    """Deprecated. Moved to POST /bookings/{booking_id}/complete."""
    from routers.bookings import complete_booking as _complete
    return await _complete(booking_id)


def _map_action_type(action_type: str) -> str:
    return {
        "phone_call": "action",
        "reminder":   "info",
        "navigation": "info",
        "button":     "action",
        "info":       "info",
        "warning":    "warning",
    }.get(action_type, "info")


def _build_message(fo: dict, status: str) -> str:
    if status == "success":
        provider = fo.get("provider", {})
        appt     = fo.get("appointment", {})
        return (
            f"Booking confirmed. "
            f"{provider.get('name', 'Provider')} will contact you before "
            f"{appt.get('scheduled_time_display', 'your appointment')}."
        )
    return fo.get("error", {}).get("message", "Service request could not be completed.")