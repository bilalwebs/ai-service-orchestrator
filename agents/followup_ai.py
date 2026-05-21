import json
import logging
import re
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage
from schemas.models import Booking, Provider
from agents.graph import llm, MODEL_PROVIDER

logger = logging.getLogger(__name__)

def get_fallback_followup(status: str, service_type: str, language: str) -> Dict[str, Any]:
    """Provide rule-based fallback actions if LLM fails."""
    # Simplified English fallback
    if status.lower() == "confirmed":
        return {
            "followup_actions": [
                {
                    "title": "Prepare the area",
                    "description": f"Please clear the area for the {service_type.replace('_', ' ')}.",
                    "action_type": "preparation",
                    "priority": "high"
                },
                {
                    "title": "Keep phone handy",
                    "description": "The provider will call you shortly.",
                    "action_type": "info",
                    "priority": "medium"
                }
            ]
        }
    elif status.lower() == "in_progress":
        return {
            "followup_actions": [
                {
                    "title": "Service Started",
                    "description": "Your service is now in progress.",
                    "action_type": "info",
                    "priority": "high"
                }
            ]
        }
    elif status.lower() == "completed":
        return {
            "followup_actions": [
                {
                    "title": "Rate your experience",
                    "description": "Please let us know how the provider did.",
                    "action_type": "review",
                    "priority": "high"
                }
            ]
        }
    else:
        return {
            "followup_actions": [
                {
                    "title": f"Status: {status}",
                    "description": f"Your booking status is now {status}.",
                    "action_type": "info",
                    "priority": "medium"
                }
            ]
        }

async def generate_followup_actions(booking: Booking, new_status: str, provider: Provider, language: str = "en") -> Dict[str, Any]:
    """
    Generate contextual, AI-powered follow-up actions based on service type and new status.
    Returns a dictionary suitable for injecting into a push notification data payload.
    """
    service_name = booking.service_type.value.replace('_', ' ').title()
    provider_name = provider.name if provider else "Your provider"
    
    system_prompt = f"""You are an AI follow-up assistant for a home services app in Pakistan.
A booking for a {service_name} has just changed status to: {new_status.upper()}.
The provider is {provider_name}.
The user prefers to communicate in: {language}. (If roman_urdu, use natural Roman Urdu).

Generate 2 to 3 contextual, highly specific next-step actions for the user.
Think about safety, preparation, or next steps specific to a {service_name}.
For example, for an electrician 'Confirmed', tell them to switch off the main breaker. For a plumber 'Completed', tell them to run the water to check for leaks.

Return ONLY a valid JSON object matching this schema:
{{
  "followup_actions": [
    {{
      "title": "Short action title (e.g., Switch off power)",
      "description": "1 sentence explanation",
      "action_type": "safety_tip | preparation | info | payment_info | review",
      "priority": "high | medium | low"
    }}
  ]
}}
"""

    prompt = f"Generate follow-up actions for {service_name} booking status: {new_status}."

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ])
        
        content = response.content.strip()
        # Clean up markdown JSON block if present
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content).strip()
        
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM response")
            
        data = json.loads(match.group())
        
        # Validate structure roughly
        if "followup_actions" not in data or not isinstance(data["followup_actions"], list):
            raise ValueError("Missing followup_actions list in JSON")
            
        logger.info(f"[FollowUpAI] Successfully generated AI follow-up for {service_name} ({new_status})")
        return data
        
    except Exception as e:
        logger.warning(f"[FollowUpAI] LLM failed to generate follow-up actions: {e}. Using fallback.")
        return get_fallback_followup(new_status, service_name, language)
