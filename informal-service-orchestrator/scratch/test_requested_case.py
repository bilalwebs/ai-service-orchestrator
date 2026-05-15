import os
import json
import sys
from dotenv import load_dotenv

# Reconfigure stdout for UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

load_dotenv()

# Force Fallback by setting an invalid key or mocking the LLM
os.environ["GOOGLE_API_KEY"] = "INVALID_KEY_FOR_TESTING_FALLBACK"

from agents.graph import app_graph
from schemas.models import ServiceRequest, Location, UrgencyLevel

def test_requested_case():
    query = "Mujhe kal subah G-13 mein AC technician chahiye."
    print(f"\n🚀 RUNNING REQUESTED TEST CASE (Forcing Fallback Mode)")
    print(f"💬 Query: \"{query}\"")
    
    request = ServiceRequest(
        user_id="user_test_99",
        raw_query=query,
        location=Location(address="G-13, Islamabad", lat=33.6333, lng=72.9667),
        urgency=UrgencyLevel.MEDIUM
    )

    initial_state = {
        "request": request,
        "intent": None,
        "language": "en",
        "urgency": "medium",
        "providers": [],
        "selected_provider": None,
        "booking": None,
        "trace": [],
        "reasoning": "",
        "final_response": None
    }

    try:
        # Run workflow
        result = app_graph.invoke(initial_state)
        
        print("\n📜 AGENT TRACE:")
        for step in result.get("trace", []):
            print(f"  {step}")

        final = result.get("final_response")
        if final:
            print("\n✨ FINAL STRUCTURED OUTPUT:")
            print(json.dumps(final, indent=2))
            
            print("\n📢 FORMATTED MESSAGE:")
            print(final.get("message"))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_requested_case()
