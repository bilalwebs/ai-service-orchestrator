import os
import json
import sys
import datetime
import re
from dotenv import load_dotenv

# Reconfigure stdout for UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

load_dotenv()

# We will manually run the nodes here to demonstrate the logic without hitting LLM quota
from agents.graph import rule_based_fallback, provider_discovery_node, ranking_node, booking_execution_node, followup_node
from schemas.models import ServiceRequest, Location, UrgencyLevel, ServiceType

def run_simulated_test():
    query = "Mujhe kal subah G-13 mein AC technician chahiye."
    print(f"\n🚀 SIMULATING REQUESTED TEST CASE (Fallback Mode Demonstration)")
    print(f"💬 Query: \"{query}\"")
    
    # 1. Intent Parser (Simulating Fallback)
    print("\n🔍 [Intent Analysis] Triggering Rule-based Fallback...")
    intent_data = rule_based_fallback(query)
    
    state = {
        "request": ServiceRequest(
            user_id="user_test_99",
            raw_query=query,
            location=Location(address="G-13, Islamabad", lat=33.6333, lng=72.9667),
            urgency=UrgencyLevel.MEDIUM
        ),
        "intent": ServiceType(intent_data["intent"]),
        "language": intent_data["language"],
        "urgency": intent_data["urgency"],
        "providers": [],
        "selected_provider": None,
        "booking": None,
        "trace": [
            f"🔍 [Intent Analysis] Input Query: '{query}'",
            f"⚙️ Analysis Source: Rule-based Fallback (LLM Quota/Error)",
            f"🎯 Service Detected: {intent_data['intent'].upper()}",
            f"⚡ Priority Level: {intent_data['urgency'].upper()}"
        ],
        "reasoning": "",
        "final_response": None
    }
    
    # 2. Discovery
    res = provider_discovery_node(state)
    state.update(res)
    
    # 3. Ranking
    res = ranking_node(state)
    state.update(res)
    
    # 4. Booking
    res = booking_execution_node(state)
    state.update(res)
    
    # 5. Follow-up
    res = followup_node(state)
    state.update(res)
    
    print("\n📜 AGENT TRACE:")
    for step in state["trace"]:
        print(f"  {step}")

    final = state["final_response"]
    if final:
        print("\n✨ FINAL STRUCTURED OUTPUT:")
        print(json.dumps(final, indent=2))
        
        print("\n📢 FORMATTED MESSAGE:")
        print(final.get("message"))

if __name__ == "__main__":
    run_simulated_test()
