# import re
# from fastapi import APIRouter, HTTPException, Path
# from schemas.models import ServiceRequest, BookingStatus
# from agents.graph import app_graph, complete_booking_node
# from tools.db_tool import db_tool
# from utils.request_id import generate_request_id
# from logs.logger import log_interaction

# router = APIRouter(prefix="/requests", tags=["Service Requests"])

# # ── Trace string → structured object ─────────────────────────────────────
# STAGE_MAP = {
#     "intent": "intent_detection",
#     "intent analysis": "intent_detection",
#     "intent parser": "intent_detection",
#     "gemini": "llm_analysis",
#     "analysis source": "llm_analysis",
#     "service detected": "service_classification",
#     "priority level": "urgency_classification",
#     "discovery": "provider_discovery",
#     "locating": "provider_discovery",
#     "found": "provider_discovery",
#     "ranking": "provider_ranking",
#     "weights": "provider_ranking",
#     "score": "provider_ranking",
#     "recommended": "provider_selection",
#     "decision rationale": "provider_selection",
#     "action": "booking_execution",
#     "booking confirmed": "booking_execution",
#     "scheduled at": "booking_execution",
#     "follow-up": "followup",
#     "workflow": "followup",
#     "reminder": "followup",
#     "no provider": "followup",
# }

# def parse_trace_string(raw_trace: list[str]) -> list[dict]:
#     """Convert raw emoji string trace into structured objects."""
#     structured = []
#     for msg in raw_trace:
#         clean = re.sub(r'[\U0001F000-\U0001FFFF☀-⟿︀-️✀-➿]+', '', msg).strip()
#         bracket = re.search(r'\[([^\]]+)\]', clean)
#         raw_stage = bracket.group(1).lower() if bracket else ""
#         body = re.sub(r'\[.*?\]\s*', '', clean).strip(' :-|')
#         stage = "trace"
#         for keyword, mapped in STAGE_MAP.items():
#             if keyword in raw_stage or keyword in body.lower():
#                 stage = mapped
#                 break
#         status = "completed"
#         if any(w in body.lower() for w in ["failed", "aborted", "error", "no provider", "no match"]):
#             status = "failed"
#         elif any(w in body.lower() for w in ["pending", "searching", "waiting"]):
#             status = "pending"
#         if body:
#             structured.append({
#                 "stage": stage,
#                 "message": body[:200],
#                 "status": status
#             })
#     return structured

# @router.post("/")
# async def create_service_request(request: ServiceRequest):
#     """Main endpoint – runs the full LangGraph workflow."""
#     # Generate unique request ID for observability
#     request_id = generate_request_id()

#     # START trace for user input received
#     from agents.graph import _make_trace
#     start_user_input = _make_trace(
#         step_name="user_input_received",
#         agent_name="router",
#         description="Received service request",
#         input_data={"raw_query": request.raw_query, "user_id": request.user_id, "location": request.location.dict() if request.location else None},
#         output_data=None,
#         reasoning="",
#         tool_used="API",
#         status="started",
#         request_id=request_id,
#     )

#     # Log request receipt
#     log_interaction(
#         request_id=request_id,
#         stage="request_received",
#         message=f"Received service request: {request.raw_query}",
#         status="success",
#         user_id=request.user_id,
#         raw_query=request.raw_query,
#         urgency=request.urgency.value,
#         location=request.location.dict() if request.location else None
#     )

#     # END trace for user input received
#     end_user_input = _make_trace(
#         step_name="user_input_received",
#         agent_name="router",
#         description="Service request logged",
#         input_data={"raw_query": request.raw_query},
#         output_data={"status": "logged"},
#         reasoning="",
#         tool_used="API",
#         status="completed",
#         request_id=request_id,
#     )

#     initial_state = {
#         "request": request,
#         "intent": None,
#         "language": request.language_detected or "en",
#         "urgency": request.urgency.value,
#         "providers": [],
#         "top_providers": [],
#         "selected_provider": None,
#         "booking": None,
#         "trace": [start_user_input, end_user_input],
#         "reasoning": "",
#         "final_response": None,
#         "request_id": request_id  # Add request_id to state for agent tracing
#     }

#     try:
#         result = app_graph.invoke(initial_state)

#         # Log successful processing
#         log_interaction(
#             request_id=request_id,
#             stage="workflow_completed",
#             message="LangGraph workflow completed successfully",
#             status="success",
#             booking_id=result.get("booking").id if result.get("booking") else None,
#             intent=result.get("intent").value if result.get("intent") else None
#         )
#     except Exception as e:
#         # Log error
#         log_interaction(
#             request_id=request_id,
#             stage="workflow_failed",
#             message=f"Workflow execution failed: {str(e)}",
#             status="error",
#             error=str(e)
#         )
#         raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")

#     fo = result.get("final_response") or {}
#     raw_trace = result.get("trace", [])
#     booking = result.get("booking")
#     status = fo.get("status", "error")

#     structured_trace = raw_trace  # Traces are now structured dicts
#     raw_steps = fo.get("next_steps", [])
#     structured_steps = []
#     for s in raw_steps:
#         structured_steps.append({
#             "step": s.get("step_number", 0),
#             "title": s.get("title", ""),
#             "description": s.get("description", ""),
#             "type": _map_action_type(s.get("action_type", "info")),
#             "action_value": s.get("action_value"),
#             "action_label": s.get("action_label")
#         })

#     return {
#         "success": status == "success",
#         "data": {
#             "status": status,
#             "message": _build_message(fo, status),
#             "service_request": fo.get("service_request", {}),
#             "provider": fo.get("provider"),
#             "appointment": fo.get("appointment"),
#             "top_providers": fo.get("top_providers"),
#             "next_steps": structured_steps,
#             "followup": fo.get("followup", {}),
#             "error": fo.get("error"),
#             "trace": structured_trace,
#         },
#         "meta": {
#             "booking_id": booking.id if booking else None,
#             "detected_intent": result.get("intent").value if result.get("intent") else None,
#             "detected_language": result.get("language"),
#             "urgency": result.get("urgency"),
#         }
#     }

# @router.post("/bookings/{booking_id}/complete")
# async def complete_booking(booking_id: str):
#     """Mark a booking as completed and update follow-up."""
#     # Generate request ID for this operation
#     request_id = generate_request_id()

#     # Log booking completion request
#     log_interaction(
#         request_id=request_id,
#         stage="booking_completion_requested",
#         message=f"Booking {booking_id} completion requested",
#         status="success"
#     )

#     # Build minimal state to invoke complete_booking_node
#     initial_state = {
#         "booking": db_tool.get_booking_by_id(booking_id),
#         "trace": [],
#         "request_id": request_id
#     }

#     try:
#         result = complete_booking_node(initial_state)

#         # Log successful booking completion
#         log_interaction(
#             request_id=request_id,
#             stage="booking_completed",
#             message=f"Booking {booking_id} marked as completed",
#             status="success",
#             result=result
#         )
#     except Exception as e:
#         # Log error
#         log_interaction(
#             request_id=request_id,
#             stage="booking_completion_failed",
#             message=f"Booking completion failed: {str(e)}",
#             status="error",
#             error=str(e)
#         )
#         raise HTTPException(status_code=500, detail=f"Booking completion failed: {str(e)}")

#     return {
#         "success": True,
#         "message": f"Booking {booking_id} marked as completed.",
#         "trace": result.get("trace", [])
#     }

# def _map_action_type(action_type: str) -> str:
#     mapping = {
#         "phone_call": "action",
#         "reminder":   "info",
#         "navigation": "info",
#         "button":     "action",
#         "info":       "info",
#         "warning":    "warning",
#     }
#     return mapping.get(action_type, "info")

# def _build_message(fo: dict, status: str) -> str:
#     if status == "success":
#         provider = fo.get("provider", {})
#         appt = fo.get("appointment", {})
#         return (
#             f"Booking confirmed. "
#             f"{provider.get('name', 'Provider')} will contact you before "
#             f"{appt.get('scheduled_time_display', 'your appointment')}."
#         )
#     error = fo.get("error", {})
#     return error.get("message", "Service request could not be completed.")


# -------------------------------------------------------------------
import re
from fastapi import APIRouter, HTTPException
from schemas.models import ServiceRequest, BookingStatus
from agents.graph import app_graph, complete_booking_node, _make_trace
from tools.db_tool import db_tool
from utils.request_id import generate_request_id
from logs.logger import log_interaction

router = APIRouter(prefix="/requests", tags=["Service Requests"])


@router.post("/")
async def create_service_request(request: ServiceRequest):
    """Main endpoint — runs the full LangGraph agentic workflow."""
    request_id = generate_request_id()

    # Trace: user input received
    start_user_input = _make_trace(
        step_name="user_input_received",
        agent_name="router",
        description="Received service request",
        input_data={
            "raw_query": request.raw_query,
            "user_id":   request.user_id,
            "location":  request.location.model_dump() if request.location else None,  # ✅ model_dump()
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
        location=request.location.model_dump() if request.location else None,  # ✅ model_dump()
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
        result = app_graph.invoke(initial_state)
        log_interaction(
            request_id=request_id,
            stage="workflow_completed",
            message="LangGraph workflow completed successfully",
            status="success",
            booking_id=result.get("booking").id if result.get("booking") else None,
            intent=result.get("intent").value if result.get("intent") else None,
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

    return {
        "success": status == "success",
        "data": {
            "status":          status,
            "message":         _build_message(fo, status),
            "service_request": fo.get("service_request", {}),
            "provider":        fo.get("provider"),
            "appointment":     fo.get("appointment"),
            "top_providers":   fo.get("top_providers"),
            "next_steps":      structured_steps,
            "followup":        fo.get("followup", {}),
            "error":           fo.get("error"),
            "trace":           result.get("trace", []),
        },
        "meta": {
            "booking_id":        booking.id if booking else None,
            "detected_intent":   result.get("intent").value if result.get("intent") else None,
            "detected_language": result.get("language"),
            "urgency":           result.get("urgency"),
            "request_id":        request_id,
        },
    }


@router.post("/bookings/{booking_id}/complete")
async def complete_booking(booking_id: str):
    """Mark a booking as completed."""
    request_id = generate_request_id()

    log_interaction(
        request_id=request_id,
        stage="booking_completion_requested",
        message=f"Booking {booking_id} completion requested",
        status="success",
    )

    initial_state = {
        "booking":    db_tool.get_booking_by_id(booking_id),
        "trace":      [],
        "request_id": request_id,
    }

    try:
        result = complete_booking_node(initial_state)
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

    return {
        "success": True,
        "message": f"Booking {booking_id} marked as completed.",
        "trace":   result.get("trace", []),
    }


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