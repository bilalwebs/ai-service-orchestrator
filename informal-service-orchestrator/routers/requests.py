# from fastapi import APIRouter, HTTPException
# from schemas.models import ServiceRequest
# from agents.graph import app_graph
# from typing import Any, Dict

# router = APIRouter(prefix="/requests", tags=["Requests"])

# @router.post("/")
# async def create_service_request(request: ServiceRequest):
#     """
#     Executes the full multi-agent workflow for a service request.
#     """
#     # Initialize the state
#     initial_state = {
#         "request": request,
#         "intent": None,
#         "language": "en",
#         "urgency": request.urgency,
#         "providers": [],
#         "selected_provider": None,
#         "booking": None,
#         "trace": [],
#         "reasoning": "",
#         "final_response": None
#     }

#     try:
#         # Run the LangGraph workflow
#         result = app_graph.invoke(initial_state)
        
#         return {
#             "status": "success",
#             "detected_intent": result.get("intent"),
#             "language": result.get("language"),
#             "final_output": result.get("final_response"),
#             "trace": result.get("trace")
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))









from fastapi import APIRouter, HTTPException
from schemas.models import ServiceRequest
from agents.graph import app_graph

router = APIRouter(prefix="/requests", tags=["Service Requests"])

@router.post("/")
async def create_service_request(request: ServiceRequest):
    """
    Antigravity Service Orchestrator - Main Endpoint
    Full Agentic Workflow: Intent Parsing → Provider Discovery → Ranking → Booking → Follow-up
    """
    initial_state = {
        "request": request,
        "intent": None,
        "language": request.language_detected or "en",
        "urgency": request.urgency.value,           # Enum ko string mein convert
        "providers": [],
        "selected_provider": None,
        "booking": None,
        "trace": [],
        "reasoning": "",
        "final_response": None
    }

    try:
        # Run the full LangGraph workflow
        result = app_graph.invoke(initial_state)
        
        return {
            "success": True,
            "message": "Service request processed successfully",
            "detected_intent": result.get("intent"),
            "detected_language": result.get("language"),
            "final_output": result.get("final_response"),
            "trace": result.get("trace", []),
            "booking_id": result.get("booking").id if result.get("booking") else None
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Workflow execution failed: {str(e)}"
        )