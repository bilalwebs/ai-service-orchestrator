# -------------------------------------------------------------------
import os
import datetime
import json
import re
import logging
from typing import TypedDict, List, Optional, Any
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from schemas.models import ServiceRequest, Provider, Booking, ServiceType, BookingStatus
from tools.database_service import db_service
from tools.maps_tool import maps_tool
from config import (
    MAX_DISTANCE_KM,
    TOP_N_PROVIDERS,
    WEIGHT_RATING,
    WEIGHT_DISTANCE,
    WEIGHT_EXPERIENCE,
    URGENCY_DISTANCE_MULTIPLIER,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Model selection (ollama or gemini)
# Default is 'ollama' as requested by the user
# -------------------------------------------------------------------
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "ollama").lower()

if MODEL_PROVIDER == "gemini":
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key or google_api_key == "your_api_key_here":
        logger.warning("GOOGLE_API_KEY is not set or placeholder. Falling back to rule-based parser in graph.")
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        google_api_key=google_api_key,
        temperature=0.1,
    )
else:
    from langchain_ollama import ChatOllama
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    logger.info(f"Using Ollama LLM provider with model: {ollama_model} on {ollama_base_url}")
    llm = ChatOllama(
        model=ollama_model,
        temperature=0.1,
        base_url=ollama_base_url,
    )


def _make_trace(step_name: str, agent_name: str, description: str, input_data: Any,
                output_data: Any, reasoning: str, tool_used: str, status: str,
                request_id: str) -> dict:
    return {
        "step_name": step_name,
        "stage": step_name,
        "agent_name": agent_name,
        "description": description,
        "message": description,
        "input": input_data,
        "output": output_data,
        "reasoning": reasoning,
        "tool_used": tool_used,
        "status": status,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "request_id": request_id,
    }


class AgentState(TypedDict):
    request: ServiceRequest
    intent: Optional[ServiceType]
    language: str
    urgency: str
    providers: List[dict]
    top_providers: List[dict]
    selected_provider: Optional[dict]
    booking: Optional[Booking]
    trace: List[dict]
    reasoning: str
    final_response: Optional[dict]
    request_id: str


def rule_based_fallback(query: str):
    query_lower = query.lower()
    keywords = {
        ServiceType.TUTOR: ["tutor", "teacher", "parhana", "parhai", "padhana", "maths",
                            "science", "physics", "home tuition", "class", "bacha", "baca",
                            "primary", "homework", "lesson", "sir", "miss", "tuition",
                            "study", "johar town"],
        ServiceType.BEAUTICIAN: ["beautician", "parlour", "makeup", "facial", "party makeup",
                                 "mehndi", "hair", "styling"],
        ServiceType.ELECTRICIAN: ["bijli", "electrician", "short circuit", "sparks",
                                  "current", "wire", "board"],
        ServiceType.PLUMBER: ["plumber", "nal", "leak", "sink", "tap", "pipe", "pipeline"],
        ServiceType.AC_TECHNICIAN: ["ac", "thanda", "cooling", "gas", "split", "cooler",
                                    "ac repair", "ac technician", "ac band"],
        ServiceType.CLEANER: ["safai", "cleaner", "cleaning", "jharu", "pocha"],
        ServiceType.PAINTER: ["painter", "paint", "rang", "white wash"],
    }
    detected_intent = ServiceType.OTHER
    for service, words in keywords.items():
        if any(word in query_lower for word in words):
            detected_intent = service
            break

    urgency = "medium"
    if any(word in query_lower for word in ["jaldi", "fauran", "foran", "emergency", "urgent",
                                             "abhi", "abhi chahiye", "sparks", "leak ho raha",
                                             "short circuit", "aag", "fire", "flood", "turant",
                                             "immediately", "right now", "asap"]):
        urgency = "high"
    elif any(word in query_lower for word in ["kal", "tomorrow", "next week", "baad mein",
                                               "agli baar", "is hafte", "this week",
                                               "next month", "plan"]):
        urgency = "low"

    urdu_markers = ["hai", "mein", "kar", "ho", "ki", "ka", "chahiye", "bhejien",
                    "parhanay", "subah", "kal", "mujhe", "aur", "se"]
    language = "roman_urdu" if any(w in query_lower for w in urdu_markers) else "en"
    return {"intent": detected_intent, "language": language, "urgency": urgency}


async def intent_parser_node(state: AgentState):
    """[NODE 1] Intent Parser — Switchable LLM + rule-based fallback."""
    request_id = state.get("request_id", "")
    query = state["request"].raw_query

    # ✅ Single start_trace only
    start_trace = _make_trace(
        step_name="intent_understanding",
        agent_name="intent_parser",
        description="Parse user query to extract service type, language, urgency",
        input_data={"raw_query": query},
        output_data=None,
        reasoning="",
        tool_used="",
        status="started",
        request_id=request_id,
    )

    system_prompt = """You are an intent parser for Antigravity Service Orchestrator.
Extract Service Type, Language, and Urgency.
Return ONLY valid JSON like: {"intent": "ac_technician", "language": "roman_urdu", "urgency": "high"}
intent values: ac_technician | plumber | electrician | tutor | cleaner | painter | beautician | other
language values: roman_urdu | urdu | en
urgency values: low | medium | high | emergency
"""
    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Query: {query}")
        ])
        content = response.content.strip()
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content).strip()
        match = re.search(r'\{[^{}]+\}', content, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM response")
        data = json.loads(match.group())
        source      = f"LLM ({MODEL_PROVIDER.upper()})"
        intent_val  = data.get("intent",   "other")
        lang_val    = data.get("language", "en")
        urgency_val = data.get("urgency",  "medium")

    except Exception as e:
        logger.warning(f"LLM invocation failed: {e}. Falling back to Rule-based parser.")
        source      = "Rule-based Fallback"
        data        = rule_based_fallback(query)
        intent_val  = data["intent"]
        lang_val    = data["language"]
        urgency_val = data["urgency"]

    try:
        intent_obj = ServiceType(intent_val)
    except ValueError:
        intent_obj = ServiceType.OTHER

    logger.info(f"Intent: {intent_obj.value}, lang: {lang_val}, urgency: {urgency_val}, source: {source}")

    # ✅ end_trace is a _make_trace dict — NO plain strings
    end_trace = _make_trace(
        step_name="intent_understanding",
        agent_name="intent_parser",
        description="Intent parsed successfully",
        input_data={"raw_query": query},
        output_data={"intent": intent_obj.value, "language": lang_val, "urgency": urgency_val},
        reasoning=f"Source: {source}. service={intent_obj.value}, language={lang_val}, urgency={urgency_val}",
        tool_used=source if source != "Rule-based Fallback" else "Rule-based",
        status="completed",
        request_id=request_id,
    )

    return {
        "intent": intent_obj,
        "language": lang_val,
        "urgency": urgency_val,
        "trace": state.get("trace", []) + [start_trace, end_trace],
    }


async def provider_discovery_node(state: AgentState):
    """[NODE 2] Provider Discovery — DB query + distance filter."""
    request_id = state.get("request_id", "")
    intent     = state["intent"]
    user_loc   = state["request"].location

    start_trace = _make_trace(
        step_name="provider_search",
        agent_name="provider_discovery",
        description="Find providers within max distance",
        input_data={
            "intent": intent.value if intent else None,
            "location": user_loc.model_dump() if user_loc else None,  # ✅ model_dump()
            "max_distance_km": MAX_DISTANCE_KM,
        },
        output_data=None,
        reasoning="",
        tool_used="",
        status="started",
        request_id=request_id,
    )

    all_providers          = db_service.get_providers_by_type(intent)
    providers_with_distance = []
    skipped_unavailable    = []
    skipped_distant        = []

    for p in all_providers:
        if not p.availability:
            skipped_unavailable.append(p.name)
            continue
        dist = maps_tool.get_distance(user_loc.lat, user_loc.lng, p.location.lat, p.location.lng)
        effective_range = min(p.range_km, MAX_DISTANCE_KM)
        if dist > effective_range:
            skipped_distant.append((p.name, round(dist, 2)))
            continue
        p_dict = p.model_dump()  # ✅ model_dump() not .dict()
        p_dict["distance"] = round(dist, 2)
        providers_with_distance.append(p_dict)

    discovery_msg = (
        f"Found {len(providers_with_distance)} providers within range."
        if providers_with_distance
        else f"No providers within range for {intent.value}."
    )
    logger.info(f"Discovery: {len(providers_with_distance)} providers found")

    end_trace = _make_trace(
        step_name="provider_search",
        agent_name="provider_discovery",
        description="Provider search completed",
        input_data=None,
        output_data={
            "providers_count": len(providers_with_distance),
            "skipped_unavailable": skipped_unavailable,
            "skipped_distant": [{"name": n, "distance_km": d} for n, d in skipped_distant],
        },
        reasoning=discovery_msg,
        tool_used="DB+Maps",
        status="completed",
        request_id=request_id,
    )

    return {
        "providers": providers_with_distance,
        "trace": state.get("trace", []) + [start_trace, end_trace],
    }


async def ranking_node(state: AgentState):
    """[NODE 3] Ranking — weighted score: rating, distance, experience."""
    request_id = state.get("request_id", "")
    providers  = state["providers"]
    urgency    = state["urgency"]

    start_trace = _make_trace(
        step_name="provider_ranking",
        agent_name="ranking",
        description="Rank providers by weighted criteria",
        input_data={"providers_count": len(providers), "urgency": urgency},
        output_data=None,
        reasoning="",
        tool_used="",
        status="started",
        request_id=request_id,
    )
    logger.info(f"Ranking: {len(providers)} providers, urgency={urgency}")

    if not providers:
        end_trace = _make_trace(
            step_name="provider_ranking",
            agent_name="ranking",
            description="No providers to rank",
            input_data=None,
            output_data={"selected_provider": None},
            reasoning="No providers found within distance limit",
            tool_used="",
            status="completed",
            request_id=request_id,
        )
        return {
            "selected_provider": None,
            "top_providers": [],
            "trace": state.get("trace", []) + [start_trace, end_trace],
        }

    dist_weight   = URGENCY_DISTANCE_MULTIPLIER.get(urgency, 1.0)
    rating_weight = WEIGHT_RATING
    exp_weight    = WEIGHT_EXPERIENCE

    for p in providers:
        p["score"] = round(
            (p["rating"] * rating_weight)
            - (p["distance"] * dist_weight)
            + (p.get("experience_years", 0) * exp_weight),
            2,
        )

    ranked   = sorted(providers, key=lambda x: x["score"], reverse=True)
    top_n    = ranked[:TOP_N_PROVIDERS]
    selected = ranked[0]

    score_log = " | ".join(
        f"{p['name']}: rating={p['rating']} dist={p['distance']}km "
        f"exp={p.get('experience_years',0)}y score={p['score']}"
        for p in ranked
    )

    reasoning = (
        f"{selected['name']} is the top match with a rating of {selected['rating']} "
        f"and is located just {selected['distance']}km away."
    )
    reasoning += (
        " Priority given to fast response time due to high urgency."
        if urgency in ["high", "emergency"]
        else " Selection optimized for service quality, reliability, and proximity."
    )

    top_providers_details = [
        {
            "rank": i,
            "provider": {
                "id": p["id"], "name": p["name"], "rating": p["rating"],
                "distance_km": p["distance"],
                "experience_years": p.get("experience_years", 0),
                "price_per_hour": p.get("price_per_hour", 1500),
                "available": True,
            },
            "score": p["score"],
            "reasoning": (
                f"Score {p['score']}: Rating {p['rating']}, "
                f"Distance {p['distance']}km, "
                f"Experience {p.get('experience_years',0)} years"
            ),
        }
        for i, p in enumerate(top_n, 1)
    ]

    end_trace = _make_trace(
        step_name="provider_ranking",
        agent_name="ranking",
        description="Ranking completed",
        input_data=None,
        output_data={
            "selected_provider": selected["name"],
            "score": selected["score"],
            "score_breakdown": score_log,
            "weights": {"rating": rating_weight, "distance": dist_weight, "experience": exp_weight},
        },
        reasoning=reasoning,
        tool_used="",
        status="completed",
        request_id=request_id,
    )

    return {
        "selected_provider": selected,
        "top_providers": top_providers_details,
        "reasoning": reasoning,
        "trace": state.get("trace", []) + [start_trace, end_trace],
    }


async def booking_execution_node(state: AgentState):
    """[NODE 4] Booking Execution — creates confirmed booking in MockDB."""
    request_id = state.get("request_id", "")
    selected   = state["selected_provider"]

    start_trace = _make_trace(
        step_name="booking_simulation",
        agent_name="booking_execution",
        description="Simulate booking creation",
        input_data={
            "provider_id": selected.get("id") if selected else None,
            "urgency": state.get("urgency"),
        },
        output_data=None,
        reasoning="",
        tool_used="",
        status="started",
        request_id=request_id,
    )

    if not selected:
        end_trace = _make_trace(
            step_name="booking_simulation",
            agent_name="booking_execution",
            description="Booking aborted — no provider",
            input_data=None, output_data=None,
            reasoning="No viable provider found",
            tool_used="", status="failed",
            request_id=request_id,
        )
        return {"trace": state.get("trace", []) + [start_trace, end_trace]}

    booking_id = f"BK-{int(datetime.datetime.now().timestamp())}"
    preferred  = state["request"].preferred_time

    if preferred:
        scheduled_at = preferred
    else:
        urgency = state["urgency"]
        now     = datetime.datetime.now()
        if urgency in ["high", "emergency"]:
            scheduled_at = (now + datetime.timedelta(hours=2)).replace(
                minute=0, second=0, microsecond=0)
        elif urgency == "low":
            scheduled_at = (now + datetime.timedelta(days=1)).replace(
                hour=10, minute=0, second=0, microsecond=0)
        else:
            scheduled_at = (now + datetime.timedelta(days=1)).replace(
                hour=9, minute=30, second=0, microsecond=0)

    booking = Booking(
        id=booking_id,
        user_id=state["request"].user_id,
        provider_id=selected["id"],
        service_type=state["intent"],
        status=BookingStatus.CONFIRMED,
        scheduled_at=scheduled_at,
        location=state["request"].location,
        total_cost=selected.get("price_per_hour", 1500),
    )
    db_service.save_booking(booking)
    logger.info(f"Booking created: {booking_id} for {selected['name']}")

    end_trace = _make_trace(
        step_name="booking_simulation",
        agent_name="booking_execution",
        description="Booking confirmed and saved to DB",
        input_data=None,
        output_data={
            "booking_id": booking_id,
            "provider": selected["name"],
            "scheduled_at": scheduled_at.isoformat(),
            "cost_per_hour": selected.get("price_per_hour", 1500),
            "status": "CONFIRMED",
        },
        reasoning=f"Booking confirmed for {selected['name']} at {scheduled_at.strftime('%I:%M %p, %d %b %Y')}",
        tool_used="DB",
        status="completed",
        request_id=request_id,
    )

    return {
        "booking": booking,
        "trace": state.get("trace", []) + [start_trace, end_trace],
    }


async def followup_node(state: AgentState):
    """[NODE 5] Follow-up — fully structured frontend-parseable JSON response."""
    booking       = state.get("booking")
    provider      = state.get("selected_provider")
    req           = state["request"]
    reasoning     = state.get("reasoning", "")
    top_providers = state.get("top_providers", [])
    request_id    = state.get("request_id", "")

    # ── NO PROVIDER CASE ────────────────────────────────────────────────
    if not provider:
        service_name = (
            state["intent"].value.replace("_", " ").title()
            if state.get("intent") else "Service"
        )
        final_response = {
            "status": "unavailable",
            "service_request": {
                "service_type": state["intent"].value if state.get("intent") else "other",
                "service_label": service_name,
                "urgency": state["urgency"].upper(),
                "raw_query": req.raw_query,
            },
            "appointment": None,
            "provider": None,
            "top_providers": [],
            "next_steps": [
                {"step_number": 1, "action": "retry",
                 "title": "Dobara try karein",
                 "description": "1-2 ghante baad dobara request karein.",
                 "action_value": None, "action_label": "Retry", "action_type": "button"},
                {"step_number": 2, "action": "contact_local",
                 "title": "Local contact karein",
                 "description": "Agar bohot urgent hai to apne local contacts se rabta karein.",
                 "action_value": None, "action_label": None, "action_type": "info"},
                {"step_number": 3, "action": "enable_notifications",
                 "title": "Notifications on karein",
                 "description": "App notifications on rakhein taake provider milne par alert mile.",
                 "action_value": None, "action_label": "Enable", "action_type": "button"},
            ],
            "followup": {
                "reminder_scheduled": False,
                "reminder_time_display": None,
                "reminder_time_iso": None,
                "status_update": "no_provider_found",
                "completion_confirmation": False,
            },
            "error": {
                "code": "NO_PROVIDER_AVAILABLE",
                "message": f"Filhal aap ke area mein {service_name} ke liye koi verified provider nahi hai.",
                "suggestion": "Kuch der baad dobara try karein.",
            },
        }
        # ✅ FIX: correct 8-space indent — inside if block
        trace_msg = _make_trace(
            step_name="followup",
            agent_name="followup",
            description="No provider available",
            input_data=None,
            output_data={"status": "unavailable"},
            reasoning=f"No {service_name} provider found in range.",
            tool_used="",
            status="completed",
            request_id=request_id,
        )

    # ── SUCCESS CASE ─────────────────────────────────────────────────────
    else:
        time_str      = booking.scheduled_at.strftime("%I:%M %p, %d %b")
        reminder_dt   = booking.scheduled_at - datetime.timedelta(hours=1)
        reminder_time = reminder_dt.strftime("%I:%M %p")
        reminder_iso  = reminder_dt.isoformat()
        scheduled_iso = booking.scheduled_at.isoformat()

        now       = datetime.datetime.now()
        diff_days = (booking.scheduled_at.date() - now.date()).days
        if diff_days == 0:
            time_desc = f"Today at {booking.scheduled_at.strftime('%I:%M %p')}"
        elif diff_days == 1:
            hour = booking.scheduled_at.hour
            if   5  <= hour < 12: time_desc = "Tomorrow morning"
            elif 12 <= hour < 17: time_desc = "Tomorrow afternoon"
            else:                 time_desc = "Tomorrow evening"
        else:
            time_desc = booking.scheduled_at.strftime("%A, %d %b at %I:%M %p")

        service_label = state["intent"].value.replace("_", " ").title()

        final_response = {
            "status": "success",
            "service_request": {
                "service_type":  state["intent"].value,
                "service_label": service_label,
                "urgency":       state["urgency"].upper(),
                "raw_query":     req.raw_query,
                "location":      req.location.address,
                "time":          time_desc,
            },
            "appointment": {
                "booking_id":             booking.id,
                "scheduled_time_display": time_str,
                "scheduled_time_iso":     scheduled_iso,
                "time_description":       time_desc,
                "slot_booked":            booking.scheduled_at.strftime("%I:%M %p"),
                "confirmation_sent":      True,
                "location": {
                    "address": req.location.address,
                    "lat":     req.location.lat,
                    "lng":     req.location.lng,
                },
                "cost_per_hour": provider.get("price_per_hour", 1500),
                "currency":      "PKR",
            },
            "provider": {
                "id":               provider.get("id"),
                "name":             provider["name"],
                "phone":            provider["phone"],
                "rating":           provider["rating"],
                "distance_km":      provider.get("distance", 0),
                "distance_display": f"{provider.get('distance', 0)} km away",
                "experience_years": provider.get("experience_years", 0),
                "reasoning":        reasoning,
            },
            "top_providers": top_providers,
            "next_steps": [
                {"step_number": 1, "action": "provider_call",
                 "title": "Provider call karega",
                 "description": f"{provider['name']} aapko 15 minutes ke andar call karega.",
                 "action_value": provider["phone"],
                 "action_label": "Call Now", "action_type": "phone_call"},
                {"step_number": 2, "action": "prepare_space",
                 "title": "Jagah tayyar karein",
                 "description": "Service ke liye relevant area clear karein.",
                 "action_value": None, "action_label": None, "action_type": "info"},
                {"step_number": 3, "action": "reminder",
                 "title": "Reminder set hai",
                 "description": f"Appointment se 1 ghanta pehle ({reminder_time}) reminder milega.",
                 "action_value": reminder_time,
                 "action_label": "Set Reminder", "action_type": "reminder"},
                {"step_number": 4, "action": "track_booking",
                 "title": "Booking track karein",
                 "description": f"Booking ID {booking.id} se apna status check karein.",
                 "action_value": booking.id,
                 "action_label": "Track", "action_type": "navigation"},
            ],
            "followup": {
                "reminder_scheduled":      True,
                "reminder_time_display":   reminder_time,
                "reminder_time_iso":       reminder_iso,
                "status_update":           "booking_confirmed",
                "completion_confirmation": False,
                "summary": f"Reminder scheduled 1 hour before appointment at {reminder_time}.",
            },
        }
        # ✅ FIX: correct 8-space indent — inside else block
        trace_msg = _make_trace(
            step_name="followup",
            agent_name="followup",
            description="Workflow completed successfully",
            input_data=None,
            output_data={"status": "success", "booking_id": booking.id},
            reasoning=f"Slot booked: {time_str}. Reminder: {reminder_time}.",
            tool_used="",
            status="completed",
            request_id=request_id,
        )

    return {
        "final_response": final_response,
        "trace": state.get("trace", []) + [trace_msg],
    }


async def complete_booking_node(state: AgentState):
    """[NODE 6] Booking Completion — marks booking COMPLETED in DB."""
    booking    = state.get("booking")
    request_id = state.get("request_id", "")

    # ✅ FIX: no-booking branch also uses _make_trace — not plain string
    if not booking:
        trace_msg = _make_trace(
            step_name="booking_completion",
            agent_name="complete_booking",
            description="No booking found to complete",
            input_data=None, output_data=None,
            reasoning="No active booking in state",
            tool_used="", status="failed",
            request_id=request_id,
        )
        return {"trace": state.get("trace", []) + [trace_msg]}

    booking.status = BookingStatus.COMPLETED
    db_service.save_booking(booking)

    trace_msg = _make_trace(
        step_name="booking_completion",
        agent_name="complete_booking",
        description="Booking marked as completed",
        input_data={"booking_id": booking.id},
        output_data={"status": "COMPLETED"},
        reasoning="Service completed by provider",
        tool_used="DB",
        status="completed",
        request_id=request_id,
    )

    return {
        "booking": booking,
        "trace": state.get("trace", []) + [trace_msg],
    }


# ── Build LangGraph ───────────────────────────────────────────────────────────
workflow = StateGraph(AgentState)
workflow.add_node("intent_parser",      intent_parser_node)
workflow.add_node("provider_discovery", provider_discovery_node)
workflow.add_node("ranking",            ranking_node)
workflow.add_node("booking_execution",  booking_execution_node)
workflow.add_node("followup",           followup_node)
workflow.add_node("complete_booking",   complete_booking_node)

workflow.set_entry_point("intent_parser")
workflow.add_edge("intent_parser",      "provider_discovery")
workflow.add_edge("provider_discovery", "ranking")
workflow.add_edge("ranking",            "booking_execution")
workflow.add_edge("booking_execution",  "followup")
workflow.add_edge("followup",           END)
workflow.add_edge("complete_booking",   END)

app_graph = workflow.compile()

