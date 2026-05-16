import os
import datetime
import json
import re
from typing import TypedDict, List, Optional
# pyrefly: ignore [missing-import]
from langgraph.graph import StateGraph, END
# pyrefly: ignore [missing-import]
from langchain_google_genai import ChatGoogleGenerativeAI
# pyrefly: ignore [missing-import]
from langchain_core.messages import HumanMessage, SystemMessage
from schemas.models import ServiceRequest, Provider, Booking, ServiceType, BookingStatus
from tools.db_tool import db_tool
from tools.maps_tool import maps_tool

# Initialize Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.2,
)

class AgentState(TypedDict):
    request: ServiceRequest
    intent: Optional[ServiceType]
    language: str
    urgency: str
    providers: List[dict]
    selected_provider: Optional[dict]
    booking: Optional[Booking]
    trace: List[str]
    reasoning: str
    final_response: Optional[dict]


def rule_based_fallback(query: str):
    """Rule-based keyword matching for intent extraction - Final Enhanced"""
    query_lower = query.lower()

    keywords = {
        ServiceType.TUTOR: [
            "tutor", "teacher", "parhana", "parhai", "padhana", "maths", "science", "physics",
            "home tuition", "class", "bacha", "baca", "primary", "homework", "lesson",
            "sir", "miss", "tuition", "study", "johar town"
        ],
        ServiceType.BEAUTICIAN: ["beautician", "parlour", "makeup", "facial", "party makeup", "mehndi", "hair", "styling"],
        ServiceType.ELECTRICIAN: ["bijli", "electrician", "short circuit", "sparks", "current", "wire", "board"],
        ServiceType.PLUMBER: ["plumber", "nal", "leak", "sink", "tap", "pipe", "pipeline"],
        ServiceType.AC_TECHNICIAN: ["ac", "thanda", "cooling", "gas", "split", "cooler", "ac repair"],
        ServiceType.CLEANER: ["safai", "cleaner", "cleaning", "jharu", "pocha"],
        ServiceType.PAINTER: ["painter", "paint", "rang", "white wash"],
    }

    detected_intent = ServiceType.OTHER
    for service, words in keywords.items():
        if any(word in query_lower for word in words):
            detected_intent = service
            break

    urgency = "medium"
    if any(word in query_lower for word in ["jaldi", "fauran", "foran", "emergency", "urgent", "abhi", "sparks", "leak ho raha"]):
        urgency = "high"
    elif any(word in query_lower for word in ["kal", "tomorrow", "next week", "baad mein"]):
        urgency = "low"

    language = "roman_urdu" if any(urdu in query_lower for urdu in ["hai", "mein", "kar", "ho", "ki", "ka", "chahiye", "bhejien", "parhanay"]) else "en"

    return {"intent": detected_intent, "language": language, "urgency": urgency}


def intent_parser_node(state: AgentState):
    """[NODE: Intent Parser] Hybrid approach using Gemini + Rule-based fallback."""
    query = state["request"].raw_query
    trace_entry = f"🔍 [Intent Analysis] Input Query: '{query}'"

    system_prompt = """
    You are an expert intent parser for 'Antigravity Service Orchestrator'.
    Extract Service Type, Language, and Urgency.
    Valid Service Types: [ac_technician, plumber, electrician, tutor, cleaner, painter, beautician, other]
    Output ONLY valid JSON like: {"intent": "ac_technician", "language": "roman_urdu", "urgency": "high"}
    """

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Query: {query}")
        ])
        content = response.content
        match = re.search(r'\{.*\}', content, re.DOTALL)
        data = json.loads(match.group()) if match else None
        if not data:
            raise ValueError("Invalid LLM JSON response")
        source = "Gemini LLM"
        intent_val = data.get("intent", "other")
        lang_val = data.get("language", "en")
        urgency_val = data.get("urgency", "medium")
        llm_log = f"🤖 [Gemini Response] intent={intent_val} | language={lang_val} | urgency={urgency_val}"

    except Exception as e:
        source = "Rule-based Fallback"
        data = rule_based_fallback(query)
        intent_val = data["intent"]
        lang_val = data["language"]
        urgency_val = data["urgency"]
        llm_log = f"⚠️ [Gemini Failed] Reason: {str(e)[:80]} → Rule-based fallback activated"

    try:
        intent_obj = ServiceType(intent_val)
    except ValueError:
        intent_obj = ServiceType.OTHER

    return {
        "intent": intent_obj,
        "language": lang_val,
        "urgency": urgency_val,
        "trace": state["trace"] + [
            trace_entry,
            llm_log,
            f"⚙️ Analysis Source: {source}",
            f"🎯 Service Detected: {intent_val.upper()}",
            f"⚡ Priority Level: {urgency_val.upper()}"
        ]
    }


def provider_discovery_node(state: AgentState):
    """[NODE: Discovery] Finds providers and calculates proximity."""
    intent = state["intent"]
    user_loc = state["request"].location
    trace_entry = f"🔎 [Discovery] Locating '{intent.value}' specialists near {user_loc.address}..."
    all_providers = db_tool.get_providers_by_type(intent)
    providers_with_distance = []
    for p in all_providers:
        dist = maps_tool.get_distance(user_loc.lat, user_loc.lng, p.location.lat, p.location.lng)
        p_dict = p.dict()
        p_dict["distance"] = round(dist, 2)
        providers_with_distance.append(p_dict)
    discovery_msg = f"📍 Found {len(providers_with_distance)} verified providers. Proximity analysis complete."
    return {
        "providers": providers_with_distance,
        "trace": state["trace"] + [trace_entry, discovery_msg]
    }


def ranking_node(state: AgentState):
    """[NODE: Ranking] Multi-criteria optimization (Rating, Distance, Urgency)."""
    providers = state["providers"]
    urgency = state["urgency"]

    if not providers:
        return {
            "selected_provider": None,
            "trace": state["trace"] + ["⚠️ [Ranking] No matching providers found in the area."]
        }

    dist_weight = 2.0 if urgency in ["high", "emergency"] else 1.0
    rating_weight = 3.0

    for p in providers:
        p["score"] = (p["rating"] * rating_weight) - (p["distance"] * dist_weight)

    ranked = sorted(providers, key=lambda x: x["score"], reverse=True)
    selected = ranked[0]

    score_log = " | ".join([
        f"{p['name']}: rating={p['rating']} dist={p['distance']}km score={round(p['score'], 2)}"
        for p in ranked
    ])

    reasoning = f"{selected['name']} is the top match with a rating of {selected['rating']} and is located just {selected['distance']}km from you."
    if urgency in ["high", "emergency"]:
        reasoning += " Priority was given to fast response time due to high urgency."
    else:
        reasoning += " Selection optimized for service quality, reliability, and proximity."

    return {
        "selected_provider": selected,
        "reasoning": reasoning,
        "trace": state["trace"] + [
            f"⚖️ [Ranking] Weights — Rating: {rating_weight}x | Distance: {dist_weight}x (Urgency: {urgency.upper()})",
            f"📊 [Score Breakdown] {score_log}",
            f"🏆 Recommended: {selected['name']} (Score: {round(selected['score'], 2)})",
            f"📝 Decision Rationale: {reasoning}"
        ]
    }


def booking_execution_node(state: AgentState):
    """[NODE: Booking] Action Simulation Node."""
    selected = state["selected_provider"]
    if not selected:
        return {"trace": state["trace"] + ["🛑 [Booking] Aborted: No viable provider."]}

    booking_id = f"BK-{int(datetime.datetime.now().timestamp())}"
    preferred = state["request"].preferred_time
    if preferred:
        scheduled_at = preferred
    else:
        tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
        scheduled_at = tomorrow.replace(hour=9, minute=30, second=0, microsecond=0)

    booking = Booking(
        id=booking_id,
        user_id=state["request"].user_id,
        provider_id=selected["id"],
        service_type=state["intent"],
        status=BookingStatus.CONFIRMED,
        scheduled_at=scheduled_at,
        location=state["request"].location,
        total_cost=selected.get("price_per_hour", 1500)
    )
    db_tool.save_booking(booking)

    return {
        "booking": booking,
        "trace": state["trace"] + [
            f"💳 [Action] Simulating API call to Provider Management System...",
            f"✅ Booking Confirmed: {booking_id} has been synced with DB.",
            f"📅 Scheduled At: {scheduled_at.strftime('%I:%M %p, %d %b %Y')} | Cost: Rs. {selected.get('price_per_hour', 1500)}/hr"
        ]
    }


def followup_node(state: AgentState):
    """[NODE: Follow-up] Fully structured JSON — frontend-parseable, no plain strings."""
    booking = state.get("booking")
    provider = state.get("selected_provider")
    req = state["request"]
    reasoning = state.get("reasoning", "")

    # ─── NO PROVIDER CASE ────────────────────────────────────────────────────
    if not provider or not booking:
        service_name = state["intent"].value.replace("_", " ").title() if state.get("intent") else "Service"

        final_response = {
            "status": "unavailable",
            "service_request": {
                "service_type": state["intent"].value if state.get("intent") else "other",
                "service_label": service_name,
                "urgency": state["urgency"].upper(),
                "raw_query": req.raw_query
            },
            "appointment": None,
            "provider": None,
            # ✅ Structured next_steps — each step is a parseable object
            "next_steps": [
                {
                    "step_number": 1,
                    "action": "retry",
                    "title": "Dobara try karein",
                    "description": "1-2 ghante baad dobara request karein.",
                    "action_value": None,
                    "action_label": "Retry",
                    "action_type": "button"       # frontend renders a button
                },
                {
                    "step_number": 2,
                    "action": "contact_local",
                    "title": "Local contact karein",
                    "description": "Agar bohot urgent hai to apne local contacts ya nearest market se rabta karein.",
                    "action_value": None,
                    "action_label": None,
                    "action_type": "info"          # frontend renders plain text
                },
                {
                    "step_number": 3,
                    "action": "enable_notifications",
                    "title": "Notifications on karein",
                    "description": "App notifications on rakhein taake provider milne par alert mile.",
                    "action_value": None,
                    "action_label": "Enable",
                    "action_type": "button"
                }
            ],
            "followup": {
                "reminder_scheduled": False,
                "reminder_time_display": None,
                "reminder_time_iso": None,
                "status_update": "no_provider_found",
                "completion_confirmation": False
            },
            "error": {
                "code": "NO_PROVIDER_AVAILABLE",
                "message": f"Filhal aap ke area mein {service_name} ke liye koi verified provider available nahi hai.",
                "suggestion": "Kuch der baad dobara try karein."
            }
        }
        trace_msg = f"⚠️ [Follow-up] No {service_name} provider available."

    # ─── SUCCESS CASE ────────────────────────────────────────────────────────
    else:
        time_str      = booking.scheduled_at.strftime("%I:%M %p, %d %b")
        reminder_dt   = booking.scheduled_at - datetime.timedelta(hours=1)
        reminder_time = reminder_dt.strftime("%I:%M %p")
        reminder_iso  = reminder_dt.isoformat()
        scheduled_iso = booking.scheduled_at.isoformat()

        final_response = {
            "status": "success",
            "service_request": {
                "service_type":  state["intent"].value,
                "service_label": state["intent"].value.replace("_", " ").title(),
                "urgency":       state["urgency"].upper(),
                "raw_query":     req.raw_query
            },
            "appointment": {
                "booking_id":             booking.id,
                "scheduled_time_display": time_str,       # human-readable
                "scheduled_time_iso":     scheduled_iso,  # machine-readable
                "location": {
                    "address": req.location.address,
                    "lat":     req.location.lat,
                    "lng":     req.location.lng
                },
                "cost_per_hour": provider.get("price_per_hour", 1500),
                "currency":      "PKR"
            },
            "provider": {
                "id":               provider.get("id"),
                "name":             provider["name"],
                "phone":            provider["phone"],
                "rating":           provider["rating"],
                "distance_km":      provider.get("distance", 0),
                "experience_years": provider.get("experience_years", 0),
                "reasoning":        reasoning
            },
            # ✅ Structured next_steps — each object is independently renderable
            "next_steps": [
                {
                    "step_number":  1,
                    "action":       "provider_call",
                    "title":        "Provider call karega",
                    "description":  f"{provider['name']} aapko 15 minutes ke andar call karega.",
                    "action_value": provider["phone"],  # use for tel: link
                    "action_label": "Call Now",
                    "action_type":  "phone_call"        # frontend: dial button
                },
                {
                    "step_number":  2,
                    "action":       "prepare_space",
                    "title":        "Jagah saaf karein",
                    "description":  "Service ke liye relevant area clear karein.",
                    "action_value": None,
                    "action_label": None,
                    "action_type":  "info"              # frontend: plain text card
                },
                {
                    "step_number":  3,
                    "action":       "reminder",
                    "title":        "Reminder mil jayega",
                    "description":  f"Appointment se 1 ghanta pehle ({reminder_time}) aapko reminder milega.",
                    "action_value": reminder_time,      # display time
                    "action_label": "Set Reminder",
                    "action_type":  "reminder"          # frontend: calendar/alarm
                },
                {
                    "step_number":  4,
                    "action":       "track_booking",
                    "title":        "Booking track karein",
                    "description":  "App mein apni booking ka real-time status dekh sakte hain.",
                    "action_value": booking.id,         # booking ID to navigate
                    "action_label": "Track",
                    "action_type":  "navigation"        # frontend: screen navigate
                }
            ],
            "followup": {
                "reminder_scheduled":    True,
                "reminder_time_display": reminder_time,
                "reminder_time_iso":     reminder_iso,  # use for local notification
                "status_update":         "booking_confirmed",
                "completion_confirmation": False
            }
        }
        trace_msg = f"🏁 [Workflow] Orchestration successfully completed. Reminder set for {reminder_time}."

    return {
        "final_response": final_response,
        "trace": state["trace"] + [trace_msg]
    }


# Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("intent_parser",      intent_parser_node)
workflow.add_node("provider_discovery", provider_discovery_node)
workflow.add_node("ranking",            ranking_node)
workflow.add_node("booking_execution",  booking_execution_node)
workflow.add_node("followup",           followup_node)

workflow.set_entry_point("intent_parser")
workflow.add_edge("intent_parser",      "provider_discovery")
workflow.add_edge("provider_discovery", "ranking")
workflow.add_edge("ranking",            "booking_execution")
workflow.add_edge("booking_execution",  "followup")
workflow.add_edge("followup",           END)

app_graph = workflow.compile()