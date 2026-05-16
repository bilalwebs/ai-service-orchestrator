# from fastapi import APIRouter, HTTPException
# from schemas.models import ServiceRequest
# from agents.graph import app_graph

# router = APIRouter(prefix="/requests", tags=["Service Requests"])

# @router.post("/")
# async def create_service_request(request: ServiceRequest):
#     """
#     Antigravity Service Orchestrator - Main Endpoint
#     Full Agentic Workflow: Intent Parsing → Provider Discovery → Ranking → Booking → Follow-up
#     """
#     initial_state = {
#         "request": request,
#         "intent": None,
#         "language": request.language_detected or "en",
#         "urgency": request.urgency.value,           # Enum ko string mein convert
#         "providers": [],
#         "selected_provider": None,
#         "booking": None,
#         "trace": [],
#         "reasoning": "",
#         "final_response": None
#     }

#     try:
#         # Run the full LangGraph workflow
#         result = app_graph.invoke(initial_state)
        
#         return {
#             "success": True,
#             "message": "Service request processed successfully",
#             "detected_intent": result.get("intent"),
#             "detected_language": result.get("language"),
#             "final_output": result.get("final_response"),
#             "trace": result.get("trace", []),
#             "booking_id": result.get("booking").id if result.get("booking") else None
#         }
#     except Exception as e:
#         raise HTTPException(
#             status_code=500, 
#             detail=f"Workflow execution failed: {str(e)}"
#         )




import re
from fastapi import APIRouter, HTTPException
from schemas.models import ServiceRequest
from agents.graph import app_graph

router = APIRouter(prefix="/requests", tags=["Service Requests"])

# ── Trace string → structured object ─────────────────────────────────────
STAGE_MAP = {
    "intent": "intent_detection",
    "intent analysis": "intent_detection",
    "intent parser": "intent_detection",
    "gemini": "llm_analysis",
    "analysis source": "llm_analysis",
    "service detected": "service_classification",
    "priority level": "urgency_classification",
    "discovery": "provider_discovery",
    "locating": "provider_discovery",
    "found": "provider_discovery",
    "ranking": "provider_ranking",
    "weights": "provider_ranking",
    "score": "provider_ranking",
    "recommended": "provider_selection",
    "decision rationale": "provider_selection",
    "action": "booking_execution",
    "booking confirmed": "booking_execution",
    "scheduled at": "booking_execution",
    "follow-up": "followup",
    "workflow": "followup",
    "reminder": "followup",
    "no provider": "followup",
}


def parse_trace_string(raw_trace: list[str]) -> list[dict]:
    """Convert raw emoji string trace into structured objects."""
    structured = []
    for msg in raw_trace:
        # Strip emojis and leading symbols
        clean = re.sub(
            r'[\U0001F000-\U0001FFFF\u2600-\u27FF\uFE00-\uFE0F\u2700-\u27BF]+',
            '', msg
        ).strip()

        # Extract [Stage Label] from brackets
        bracket = re.search(r'\[([^\]]+)\]', clean)
        raw_stage = bracket.group(1).lower() if bracket else ""

        # Remove the bracket from message body
        body = re.sub(r'\[.*?\]\s*', '', clean).strip(' :-|')

        # Map to structured stage
        stage = "trace"
        for keyword, mapped in STAGE_MAP.items():
            if keyword in raw_stage or keyword in body.lower():
                stage = mapped
                break

        # Determine status
        status = "completed"
        if any(w in body.lower() for w in ["failed", "aborted", "error", "no provider", "no match"]):
            status = "failed"
        elif any(w in body.lower() for w in ["pending", "searching", "waiting"]):
            status = "pending"

        if body:
            structured.append({
                "stage": stage,
                "message": body[:200],
                "status": status
            })
    return structured


@router.post("/")
async def create_service_request(request: ServiceRequest):
    """
    Antigravity Service Orchestrator — Main Endpoint
    Returns STRICT STRUCTURED JSON only. Frontend-parseable.
    """
    initial_state = {
        "request": request,
        "intent": None,
        "language": request.language_detected or "en",
        "urgency": request.urgency.value,
        "providers": [],
        "selected_provider": None,
        "booking": None,
        "trace": [],
        "reasoning": "",
        "final_response": None
    }

    try:
        result = app_graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Workflow execution failed: {str(e)}"
        )

    fo = result.get("final_response") or {}
    raw_trace = result.get("trace", [])
    booking = result.get("booking")
    status = fo.get("status", "error")

    # ── Build structured trace ────────────────────────────────────────────
    structured_trace = parse_trace_string(raw_trace)

    # ── Normalize next_steps (already structured from followup_node) ──────
    raw_steps = fo.get("next_steps", [])
    structured_steps = []
    for s in raw_steps:
        structured_steps.append({
            "step": s.get("step_number", 0),
            "title": s.get("title", ""),
            "description": s.get("description", ""),
            "type": _map_action_type(s.get("action_type", "info")),
            "action_value": s.get("action_value"),
            "action_label": s.get("action_label")
        })

    # ── Final strict response ─────────────────────────────────────────────
    return {
        "success": status == "success",
        "data": {
            "status": status,
            "message": _build_message(fo, status),
            "service_request": fo.get("service_request", {}),
            "provider": fo.get("provider"),
            "appointment": fo.get("appointment"),
            "next_steps": structured_steps,
            "followup": fo.get("followup", {}),
            "error": fo.get("error"),
            "trace": structured_trace,
        },
        "meta": {
            "booking_id": booking.id if booking else None,
            "detected_intent": result.get("intent").value if result.get("intent") else None,
            "detected_language": result.get("language"),
            "urgency": result.get("urgency"),
        }
    }


def _map_action_type(action_type: str) -> str:
    """Normalize action_type to frontend-safe enum."""
    mapping = {
        "phone_call": "action",
        "reminder":   "info",
        "navigation": "info",
        "button":     "action",
        "info":       "info",
        "warning":    "warning",
    }
    return mapping.get(action_type, "info")


def _build_message(fo: dict, status: str) -> str:
    if status == "success":
        provider = fo.get("provider", {})
        appt = fo.get("appointment", {})
        return (
            f"Booking confirmed. "
            f"{provider.get('name', 'Provider')} will contact you before "
            f"{appt.get('scheduled_time_display', 'your appointment')}."
        )
    error = fo.get("error", {})
    return error.get("message", "Service request could not be completed.")