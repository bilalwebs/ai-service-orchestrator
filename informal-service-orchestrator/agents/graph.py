import os
import datetime
import json
import re
from typing import TypedDict, List, Optional, Annotated
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
    model="gemini-2.0-flash", 
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

# def rule_based_fallback(query: str):
#     """Rule-based keyword matching for intent extraction."""
#     query = query.lower()
    
#     # Intent keywords
#     keywords = {
#         ServiceType.AC_TECHNICIAN: ["ac", "air condition", "thanda", "cooling", "gas", "servicing", "filter"],
#         ServiceType.PLUMBER: ["plumber", "nal", "leak", "tanki", "pipeline", "sink", "washroom", "tap"],
#         ServiceType.ELECTRICIAN: ["bijli", "electrician", "short circuit", "fan", "board", "light", "sparks", "switch"],
#         ServiceType.TUTOR: ["tutor", "teacher", "parhana", "maths", "physics", "home tuition", "parhai"],
#         ServiceType.CLEANER: ["safai", "cleaner", "cleaning", "jharu", "pocha", "deep cleaning", "dusting"],
#         ServiceType.PAINTER: ["painter", "rang", "paint", "white wash", "deewar"],
#         ServiceType.BEAUTICIAN: ["parlour", "beautician", "makeup", "facial", "threading", "hair", "styling"],
#     }
    
#     detected_intent = ServiceType.OTHER
#     for service, words in keywords.items():
#         if any(word in query for word in words):
#             detected_intent = service
#             break
            
#     # Urgency keywords
#     urgency = "medium"
#     if any(word in query for word in ["jaldi", "fauran", "emergency", "urgent", "sparks", "leak ho raha"]):
#         urgency = "high"
#     elif any(word in query for word in ["chill", "jab time mile", "next week", "later"]):
#         urgency = "low"
        
#     # Language detection
#     language = "en"
#     if any(word in query for word in ["hai", "ka", "ki", "mein", "kar", "ho"]):
#         language = "roman_urdu"
        
#     return {
#         "intent": detected_intent,
#         "language": language,
#         "urgency": urgency
#     }

def rule_based_fallback(query: str):
    """Rule-based keyword matching for intent extraction - Final Enhanced"""
    query_lower = query.lower()
    
    # Priority order: Most specific first
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
            break   # Important: First match ko priority do
    
    # Urgency
    urgency = "medium"
    if any(word in query_lower for word in ["jaldi", "fauran", "foran", "emergency", "urgent", "abhi", "sparks", "leak ho raha"]):
        urgency = "high"
    elif any(word in query_lower for word in ["kal", "tomorrow", "next week", "baad mein"]):
        urgency = "low"
        
    # Language
    language = "roman_urdu" if any(urdu in query_lower for urdu in ["hai", "mein", "kar", "ho", "ki", "ka", "chahiye", "bhejien", "parhanay"]) else "en"
    
    return {
        "intent": detected_intent,
        "language": language,
        "urgency": urgency
    }
def intent_parser_node(state: AgentState):
    """[NODE: Intent Parser] Hybrid approach using Gemini + Rule-based fallback."""
    query = state["request"].raw_query
    trace_entry = f"🔍 [Intent Analysis] Input Query: '{query}'"
    
    system_prompt = """
    You are an expert intent parser for 'Antigravity Service Orchestrator'.
    Extract Service Type, Language, and Urgency.
    Valid Service Types: [ac_technician, plumber, electrician, tutor, cleaner, painter, beautician, other]
    Output ONLY valid JSON.
    """
    
    try:
        # Attempt LLM analysis
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
        
    except Exception as e:
        # Fallback to Rule-based logic
        source = "Rule-based Fallback"
        data = rule_based_fallback(query)
        intent_val = data["intent"]
        lang_val = data["language"]
        urgency_val = data["urgency"]
    
    # === SAFE INTENT CONVERSION (Added) ===
    try:
        intent_obj = ServiceType(intent_val)
    except ValueError:
        intent_obj = ServiceType.OTHER
    
    return {
        "intent": intent_obj,                    # Safe conversion
        "language": lang_val,
        "urgency": urgency_val,
        "trace": state["trace"] + [
            trace_entry,
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
    
    # FIXED: Method name corrected (MockDB mein get_providers_by_type hai)
    all_providers = db_tool.get_providers_by_type(intent)
    
    # Calculate distances
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

# def ranking_node(state: AgentState):
#     """[NODE: Ranking] Multi-criteria optimization (Rating, Distance, Urgency)."""
#     providers = state["providers"]
#     urgency = state["urgency"]
    
#     if not providers:
#         # Resilience check: If we have NO providers for this type, don't just fail.
#         return {
#             "selected_provider": None, 
#             "trace": state["trace"] + ["⚠️ [Ranking] No matching providers found in the area."]
#         }
    
#     # Weighting logic
#     dist_weight = 2.0 if urgency in ["high", "emergency"] else 1.0
#     rating_weight = 3.0
    
#     for p in providers:
#         p["score"] = (p["rating"] * rating_weight) - (p["distance"] * dist_weight)
        
#     ranked = sorted(providers, key=lambda x: x["score"], reverse=True)
#     selected = ranked[0]
    
#     reasoning = f"{selected['name']} is the top match with a rating of {selected['rating']} and is located just {selected['distance']}km from you. "
#     if urgency in ["high", "emergency"]:
#         reasoning += "Priority was given to fast response time due to high urgency."
#     else:
#         reasoning += "Selection optimized for service quality and reliability."
        
#     return {
#         "selected_provider": selected,
#         "reasoning": reasoning,
#         "trace": state["trace"] + [
#             "⚖️ [Ranking] Evaluating provider scores based on Urgency Weights...",
#             f"🏆 Recommended: {selected['name']} (Score: {round(selected['score'], 2)})",
#             f"📝 Decision Rationale: {reasoning}"
#         ]
#     }


def ranking_node(state: AgentState):
    """[NODE: Ranking] Multi-criteria optimization (Rating, Distance, Urgency)."""
    providers = state["providers"]
    urgency = state["urgency"]
    
    if not providers:
        return {
            "selected_provider": None, 
            "trace": state["trace"] + ["⚠️ [Ranking] No matching providers found in the area."]
        }
    
    # Weighting logic
    dist_weight = 2.0 if urgency in ["high", "emergency"] else 1.0
    rating_weight = 3.0
    
    for p in providers:
        p["score"] = (p["rating"] * rating_weight) - (p["distance"] * dist_weight)
        
    ranked = sorted(providers, key=lambda x: x["score"], reverse=True)
    selected = ranked[0]
    
    # Improved Reasoning Text
    reasoning = f"{selected['name']} is the top match with a rating of {selected['rating']} and is located just {selected['distance']}km from you."
    if urgency in ["high", "emergency"]:
        reasoning += " Priority was given to fast response time due to high urgency."
    else:
        reasoning += " Selection optimized for service quality, reliability, and proximity."
    
    return {
        "selected_provider": selected,
        "reasoning": reasoning,
        "trace": state["trace"] + [
            "⚖️ [Ranking] Evaluating provider scores based on Urgency Weights...",
            f"🏆 Recommended: {selected['name']} (Score: {round(selected['score'], 2)})",
            f"📝 Decision Rationale: {reasoning}"
        ]
    }


# def booking_execution_node(state: AgentState):
#     """[NODE: Booking] Action Simulation Node."""
#     selected = state["selected_provider"]
#     if not selected:
#         return {"trace": state["trace"] + ["🛑 [Booking] Aborted: No viable provider."]}
    
#     booking_id = f"BK-{int(datetime.datetime.now().timestamp())}"
#     booking = Booking(
#         id=booking_id,
#         user_id=state["request"].user_id,
#         provider_id=selected["id"],
#         service_type=state["intent"],
#         status=BookingStatus.CONFIRMED,
#         scheduled_at=state["request"].preferred_time or datetime.datetime.now() + datetime.timedelta(hours=2),
#         location=state["request"].location,
#         total_cost=selected["price_per_hour"]
#     )
    
#     db_tool.save_booking(booking)
    
#     return {
#         "booking": booking,
#         "trace": state["trace"] + [
#             f"💳 [Action] Simulating API call to Provider Management System...",
#             f"✅ Booking Confirmed: {booking_id} has been synced with DB."
#         ]
#     }

def booking_execution_node(state: AgentState):
    """[NODE: Booking] Action Simulation Node."""
    selected = state["selected_provider"]
    if not selected:
        return {"trace": state["trace"] + ["🛑 [Booking] Aborted: No viable provider."]}
    
    booking_id = f"BK-{int(datetime.datetime.now().timestamp())}"
    
    # Improved Time Logic
    preferred = state["request"].preferred_time
    if preferred:
        scheduled_at = preferred
    else:
        # Next day morning 9:30 AM (better for demo)
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
            f"✅ Booking Confirmed: {booking_id} has been synced with DB."
        ]
    }

# def followup_node(state: AgentState):
#     """[NODE: Follow-up] Final User-Facing Response Generation."""
#     booking = state["booking"]
#     provider = state["selected_provider"]
#     req = state["request"]
#     reasoning = state.get("reasoning", "")
    
#     if not booking:
#         final_response = {
#             "status": "failure",
#             "message": "Maazrat! Filhal koi provider mil nahi saka. / Sorry, no provider found.",
#             "trace_id": f"TR-{int(datetime.datetime.now().timestamp())}"
#         }
#     else:
#         time_str = booking.scheduled_at.strftime("%I:%M %p, %d %b")
        
#         final_response = {
#             "service_request": {
#                 "type": state["intent"].value.replace("_", " ").title(),
#                 "urgency": state["urgency"].upper(),
#                 "query": req.raw_query
#             },
#             "appointment": {
#                 "location": req.location.address,
#                 "scheduled_time": time_str,
#                 "booking_id": booking.id
#             },
#             "recommendation": {
#                 "provider_name": provider["name"],
#                 "contact": provider["phone"],
#                 "rating": provider["rating"],
#                 "distance": f"{provider['distance']} km",
#                 "why_this_provider": reasoning
#             },
#             "next_steps": [
#                 f"1. {provider['name']} will call you on {provider['phone']} within 15 minutes.",
#                 "2. Please keep the workplace clear for the service.",
#                 "3. You can track the arrival status in the app."
#             ],
#             "message": f"Behtreen! {provider['name']} confirm ho gaye hain. Woh {time_str} par pohoch jayain gay. \n\nGreat! {provider['name']} is confirmed for {time_str}."
#         }
            
#     return {
#         "final_response": final_response,
#         "trace": state["trace"] + ["🏁 [Workflow] Orchestration successfully completed."]
#     }


def followup_node(state: AgentState):
    """[NODE: Follow-up] Final User-Facing Response Generation with Reminder."""
    booking = state.get("booking")
    provider = state.get("selected_provider")
    req = state["request"]
    reasoning = state.get("reasoning", "")

    if not provider or not booking:
        service_name = state["intent"].value.replace("_", " ").title() if state.get("intent") else "Service"
        
        final_response = {
            "status": "unavailable",
            "message": f"Maazrat! Filhal aap ke area mein **{service_name}** ke liye koi verified provider available nahi hai.",
            "suggestion": "Kuch der baad (1-2 ghante) dobara try karein. Hum providers ko continuously check kar rahe hain.",
            "service_request": {
                "type": service_name,
                "urgency": state["urgency"].upper(),
                "query": req.raw_query
            },
            "appointment": {
                "location": req.location.address,
                "scheduled_time": "N/A",
                "booking_id": "N/A"
            },
            "recommendation": {
                "provider_name": "Koi Provider Available Nahi",
                "contact": "N/A",
                "rating": "N/A",
                "distance": "N/A",
                "why_this_provider": "Currently no matching provider found in your area."
            },
            "next_steps": [
                "1. 1-2 ghante baad dobara request karein.",
                "2. Agar bohot urgent hai to apne local contacts ya nearest market se rabta karein.",
                "3. App notifications on rakhein."
            ]
        }
        trace_msg = f"⚠️ [Follow-up] No {service_name} provider available."
        
    else:
        # === SAFETY CHECK ===
        if not provider or not booking:
            final_response = {
                "status": "error",
                "message": "Maazrat! Koi technical issue aa gaya hai. Kripya dobara try karein."
            }
            trace_msg = "❌ [Follow-up] Safety check failed."
        else:
            time_str = booking.scheduled_at.strftime("%I:%M %p, %d %b")
            reminder_time = (booking.scheduled_at - datetime.timedelta(hours=1)).strftime("%I:%M %p")
            
            final_response = {
                "status": "success",
                "message": f"Behtreen! {provider['name']} confirm ho gaye hain. Woh {time_str} par pohoch jayain gay.\n\nGreat! {provider['name']} is confirmed for {time_str}.",
                "service_request": {
                    "type": state["intent"].value.replace("_", " ").title(),
                    "urgency": state["urgency"].upper(),
                    "query": req.raw_query
                },
                "appointment": {
                    "location": req.location.address,
                    "scheduled_time": time_str,
                    "booking_id": booking.id,
                    "reminder": f"1 hour before reminder scheduled at {reminder_time}"
                },
                "recommendation": {
                    "provider_name": provider["name"],
                    "contact": provider["phone"],
                    "rating": provider["rating"],
                    "distance": f"{provider.get('distance', 'N/A')} km",
                    "why_this_provider": reasoning
                },
                "next_steps": [
                    f"1. {provider['name']} aapko {provider['phone']} par 15 minutes ke andar call karenge.",
                    "2. Service ke liye jagah saaf rakhein.",
                    f"3. Appointment se **1 ghanta pehle** ({reminder_time}) reminder mil jayega.",
                    "4. App mein booking track kar sakte hain."
                ]
            }
            trace_msg = f"🏁 [Workflow] Orchestration successfully completed. Reminder scheduled."

    return {
        "final_response": final_response,
        "trace": state["trace"] + [trace_msg]
    }


# Build Graph
workflow = StateGraph(AgentState)
workflow.add_node("intent_parser", intent_parser_node)
workflow.add_node("provider_discovery", provider_discovery_node)
workflow.add_node("ranking", ranking_node)
workflow.add_node("booking_execution", booking_execution_node)
workflow.add_node("followup", followup_node)

workflow.set_entry_point("intent_parser")
workflow.add_edge("intent_parser", "provider_discovery")
workflow.add_edge("provider_discovery", "ranking")
workflow.add_edge("ranking", "booking_execution")
workflow.add_edge("booking_execution", "followup")
workflow.add_edge("followup", END)

app_graph = workflow.compile()
