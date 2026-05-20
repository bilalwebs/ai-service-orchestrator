import asyncio
import json
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from schemas.models import ServiceRequest, AdminRequestLog
from agents.graph import (
    app_graph, complete_booking_node, _make_trace, llm,
    intent_parser_node, provider_discovery_node,
    ranking_node, booking_execution_node, followup_node,
)
from langchain_core.messages import HumanMessage, SystemMessage
from tools.database_service import db_service
from utils.request_id import generate_request_id
from logs.logger import log_interaction
from schemas.response import api_response

router = APIRouter(prefix="/requests", tags=["Service Requests"])

# Timeout (seconds) for the full LangGraph workflow. Guards against LLM hangs.
WORKFLOW_TIMEOUT_SECONDS = int(__import__("os").getenv("WORKFLOW_TIMEOUT_SECONDS", "60"))

FIXED_PLAN_STEPS = [
    {"stage": "intent_detection",       "status": "waiting"},
    {"stage": "llm_analysis",           "status": "waiting"},
    {"stage": "service_classification", "status": "waiting"},
    {"stage": "urgency_classification", "status": "waiting"},
    {"stage": "provider_discovery",     "status": "waiting"},
    {"stage": "provider_ranking",       "status": "waiting"},
    {"stage": "provider_selection",     "status": "waiting"},
    {"stage": "booking_execution",      "status": "waiting"},
    {"stage": "followup",               "status": "waiting"},
]


async def _get_plan_message(query: str) -> str:
    """Quick LLM call: one warm sentence in the same language as the query."""
    try:
        response = await asyncio.wait_for(
            llm.ainvoke([
                SystemMessage(content=(
                    "You are an AI assistant for a home services booking app in Pakistan.\n"
                    "Given a user's service request, write ONE brief sentence (under 15 words) "
                    "in the SAME language/script as the query.\n"
                    "Acknowledge warmly and say what you will do. Return ONLY the sentence.\n\n"
                    "Examples:\n"
                    "Query: Mujhe kal subah G-13 mein AC technician chahiye\n"
                    "Response: G-13 mein aap ke liye kal subah AC technician dhundh raha hoon.\n\n"
                    "Query: I need an electrician urgently\n"
                    "Response: Finding a certified electrician near you right now.\n\n"
                    "Query: plumber chahiye leak hai\n"
                    "Response: Aap ke area mein trusted plumber abhi dhundh raha hoon."
                )),
                HumanMessage(content=f"Query: {query}"),
            ]),
            timeout=15.0,
        )
        return response.content.strip()
    except Exception:
        return "Finding the best service provider for you, please wait..."


# Global registry to track active asyncio tasks by request_id
active_tasks: Dict[str, asyncio.Task] = {}


@router.post("/")
async def create_service_request(request: ServiceRequest):
    """Main endpoint — runs the full LangGraph agentic workflow."""
    request_id = generate_request_id()
    active_tasks[request_id] = asyncio.current_task()

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
    except asyncio.CancelledError:
        log_interaction(
            request_id=request_id,
            stage="workflow_cancelled",
            message="LangGraph workflow was cancelled by the user",
            status="cancelled",
        )
        db_service.log_request(AdminRequestLog(
            id=request_id,
            user_id=request.user_id,
            raw_query=request.raw_query,
            urgency=request.urgency.value,
            intent=None,
            language="en",
            status="cancelled",
            booking_id=None,
            trace=initial_state.get("trace", []),
            created_at=datetime.now().isoformat()
        ))
        raise HTTPException(status_code=499, detail="Request cancelled by client")
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
    finally:
        active_tasks.pop(request_id, None)

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

    async def event_stream():
        active_tasks[request_id] = asyncio.current_task()
        final_state = dict(initial_state)
        try:
            # ── 1. Connected immediately ─────────────────────────────────────
            yield f"data: {json.dumps({'event': 'connected', 'request_id': request_id})}\n\n"

            # ── 2. LLM plan message (15s timeout → fallback) ─────────────────
            plan_message = await _get_plan_message(request.raw_query)
            yield f"data: {json.dumps({'event': 'plan', 'message': plan_message, 'steps': FIXED_PLAN_STEPS})}\n\n"

            # ── 3. Intent parsing ─────────────────────────────────────────────
            yield f"data: {json.dumps({'event': 'step_start', 'stage': 'intent_detection'})}\n\n"
            intent_result = await intent_parser_node(final_state)
            final_state = {**final_state, **intent_result}
            intent_val  = final_state.get("intent")
            intent_str  = intent_val.value if intent_val else "unknown"
            lang_str    = final_state.get("language", "en")
            urgency_str = final_state.get("urgency", "medium")
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'intent_detection',       'message': 'Request understood'})}\n\n"
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'llm_analysis',           'message': f'Language: {lang_str}'})}\n\n"
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'service_classification', 'message': f'Service: {intent_str}'})}\n\n"
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'urgency_classification', 'message': f'Urgency: {urgency_str}'})}\n\n"

            # ── 4. Provider discovery ─────────────────────────────────────────
            yield f"data: {json.dumps({'event': 'step_start', 'stage': 'provider_discovery'})}\n\n"
            discovery_result = await provider_discovery_node(final_state)
            final_state = {**final_state, **discovery_result}
            provider_count = len(final_state.get("providers", []))
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'provider_discovery', 'message': f'{provider_count} providers found nearby'})}\n\n"

            # ── 5. Ranking → two step_completes ──────────────────────────────
            yield f"data: {json.dumps({'event': 'step_start', 'stage': 'provider_ranking'})}\n\n"
            ranking_result = await ranking_node(final_state)
            final_state   = {**final_state, **ranking_result}
            selected      = final_state.get("selected_provider")
            selected_name = selected.get("name") if selected else "None available"
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'provider_ranking',   'message': 'Providers ranked by rating and distance'})}\n\n"
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'provider_selection', 'message': f'Selected: {selected_name}'})}\n\n"

            # ── 6. Booking ────────────────────────────────────────────────────
            yield f"data: {json.dumps({'event': 'step_start', 'stage': 'booking_execution'})}\n\n"
            booking_result = await booking_execution_node(final_state)
            final_state    = {**final_state, **booking_result}
            booking        = final_state.get("booking")
            if booking:
                slot_str = booking.scheduled_at.strftime("%I:%M %p, %d %b")
                yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'booking_execution', 'message': f'Slot booked: {slot_str}'})}\n\n"
                yield f"data: {json.dumps({'event': 'booking_ready', 'booking_id': booking.id})}\n\n"
            else:
                yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'booking_execution', 'message': 'No provider available in range'})}\n\n"

            # ── 7. Follow-up ──────────────────────────────────────────────────
            yield f"data: {json.dumps({'event': 'step_start', 'stage': 'followup'})}\n\n"
            followup_result = await followup_node(final_state)
            final_state     = {**final_state, **followup_result}
            yield f"data: {json.dumps({'event': 'step_complete', 'stage': 'followup', 'message': 'Reminder scheduled 1 hour before appointment'})}\n\n"

            log_interaction(
                request_id=request_id,
                stage="workflow_completed",
                message="Stream workflow completed successfully",
                status="success",
                booking_id=booking.id if booking else None,
                intent=intent_str,
            )

        except asyncio.CancelledError:
            log_interaction(
                request_id=request_id,
                stage="workflow_cancelled",
                message="LangGraph stream cancelled by user request",
                status="cancelled",
            )
            db_service.log_request(AdminRequestLog(
                id=request_id,
                user_id=request.user_id,
                raw_query=request.raw_query,
                urgency=request.urgency.value,
                intent=None,
                language="en",
                status="cancelled",
                booking_id=None,
                trace=initial_state.get("trace", []),
                created_at=datetime.now().isoformat()
            ))
            yield f"data: {json.dumps({'event': 'cancelled', 'detail': 'Request cancelled by user'})}\n\n"
            raise
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'event': 'error', 'detail': 'Stream timed out'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'detail': str(e)})}\n\n"
        finally:
            active_tasks.pop(request_id, None)
            intent_val = final_state.get("intent")
            booking    = final_state.get("booking")
            db_service.log_request(AdminRequestLog(
                id=request_id,
                user_id=request.user_id,
                raw_query=request.raw_query,
                urgency=request.urgency.value,
                intent=intent_val.value if intent_val else None,
                language=final_state.get("language", "en"),
                status="success" if booking else "no_provider",
                booking_id=booking.id if booking else None,
                trace=final_state.get("trace", []),
                created_at=datetime.now().isoformat()
            ))
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


@router.post("/{request_id}/cancel")
async def cancel_service_request(request_id: str):
    """Cancel a running request by ID."""
    task = active_tasks.get(request_id)
    if task:
        task.cancel()
        existing_log = db_service.get_request_log_by_id(request_id)
        if existing_log:
            existing_log.status = "cancelled"
            db_service.log_request(existing_log)
        else:
            db_service.log_request(AdminRequestLog(
                id=request_id,
                user_id="unknown",
                raw_query="Cancelled request",
                urgency="medium",
                intent=None,
                language="en",
                status="cancelled",
                booking_id=None,
                trace=[],
                created_at=datetime.now().isoformat()
            ))
        return api_response(success=True, message="Request cancellation request sent successfully.")
    else:
        existing_log = db_service.get_request_log_by_id(request_id)
        if existing_log:
            existing_log.status = "cancelled"
            db_service.log_request(existing_log)
            return api_response(success=True, message="Request marked as cancelled in database.")
        return api_response(success=False, message="Request not found or already completed.")


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