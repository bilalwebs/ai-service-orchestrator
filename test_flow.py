# import os
# import json
# import sys
# from dotenv import load_dotenv

# # Reconfigure stdout for UTF-8 to handle emojis in Windows terminals
# if sys.stdout.encoding != 'utf-8':
#     try:
#         sys.stdout.reconfigure(encoding='utf-8')
#     except AttributeError:
#         # Fallback for older python versions
#         import codecs
#         sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# # Load environment variables
# load_dotenv()

# from agents.graph import app_graph
# from schemas.models import ServiceRequest, Location, UrgencyLevel

# def run_test_case(title, query, location_name, lat, lng):
#     print("\n" + "="*80)
#     print(f"🚀 TEST CASE: {title}")
#     print(f"💬 Query: \"{query}\"")
#     print(f"📍 Location: {location_name}")
#     print("="*80)

#     request = ServiceRequest(
#         user_id="test_user_123",
#         raw_query=query,
#         location=Location(address=location_name, lat=lat, lng=lng),
#         urgency=UrgencyLevel.MEDIUM
#     )

#     initial_state = {
#         "request": request,
#         "intent": None,
#         "language": "en",
#         "urgency": "medium",
#         "providers": [],
#         "selected_provider": None,
#         "booking": None,
#         "trace": [],
#         "reasoning": "",
#         "final_response": None
#     }

#     try:
#         result = app_graph.invoke(initial_state)
        
#         print("\n📜 AGENT TRACE (Step-by-Step Reasoning):")
#         for step in result.get("trace", []):
#             print(f"  {step}")

#         final = result.get("final_response")
#         if final and final.get("message"):
#             print("\n✨ FINAL STRUCTURED OUTPUT:")
#             print(f"📢 Status: {final['message']}")
#             print("-" * 50)
            
#             if "service_request" in final:
#                 sr = final["service_request"]
#                 print(f"🛠️  SERVICE:   {sr['type']} ({sr['urgency']})")
                
#             if "appointment" in final:
#                 ap = final["appointment"]
#                 print(f"📍 LOCATION:  {ap['location']}")
#                 print(f"⏰ TIME:      {ap['scheduled_time']}")
#                 print(f"🆔 BOOKING:   {ap['booking_id']}")
                
#             print("-" * 50)
            
#             if "recommendation" in final:
#                 rec = final["recommendation"]
#                 print(f"👤 PROVIDER:   {rec['provider_name']}")
#                 print(f"📞 CONTACT:    {rec['contact']}")
#                 print(f"⭐ RATING:     {rec['rating']} | 📏 DIST: {rec['distance']}")
#                 print(f"🧠 REASONING:  {rec['why_this_provider']}")
                
#             print("-" * 50)
            
#             if "next_steps" in final:
#                 print("📝 NEXT STEPS:")
#                 for step in final["next_steps"]:
#                     print(f"  {step}")
#         else:
#             print(f"\n❌ FAILED: {final.get('message') if final else 'No response'}")

#     except Exception as e:
#         print(f"\n💥 CRITICAL ERROR: {str(e)}")

# if __name__ == "__main__":
#     # Test cases with Pakistani locations
#     test_cases = [
#         {
#             "title": "AC Technician (Specific Request) - G-13",
#             "query": "Mujhe kal subah G-13 mein AC technician chahiye.",
#             "location": "G-13, Islamabad",
#             "lat": 33.6333, "lng": 72.9667
#         },
#         {
#             "title": "AC Technician (Roman Urdu) - Karachi",
#             "query": "Mera AC thanda nahi kar raha, gas check karwani hai. Jaldi bhejien.",
#             "location": "North Nazimabad, Karachi",
#             "lat": 24.9333, "lng": 67.0333
#         },
#         {
#             "title": "Plumber (English) - Islamabad G-13",
#             "query": "My kitchen tap is leaking since morning, need a plumber in G-13 Islamabad.",
#             "location": "G-13, Islamabad",
#             "lat": 33.6333, "lng": 72.9667
#         },
#         {
#             "title": "Electrician (Emergency) - Lahore",
#             "query": "Short circuit in the main board, sparks coming out! Fauran bhejien bijli wala.",
#             "location": "Gulberg III, Lahore",
#             "lat": 31.5100, "lng": 74.3400
#         },
#         {
#             "title": "Beautician (Party Makeup) - Islamabad F-6",
#             "query": "Need a beautician for party makeup at home in F-6 Islamabad for tomorrow 4pm.",
#             "location": "F-6, Islamabad",
#             "lat": 33.7297, "lng": 73.0747
#         },
#         {
#             "title": "Home Tutor (Urdu Query) - Lahore",
#             "query": "Bacha primary class mein hai, Maths aur Science parhanay k liye teacher chahiye Johar Town mein.",
#             "location": "Johar Town, Lahore",
#             "lat": 31.4697, "lng": 74.2728
#         }
#     ]

#     print("🛠️  ANTIGRAVITY SERVICE ORCHESTRATOR - FULL WORKFLOW TEST SUITE 🛠️")
#     print("Testing multi-agent orchestration for informal economy services in Pakistan.")
    
#     for tc in test_cases:
#         run_test_case(tc["title"], tc["query"], tc["location"], tc["lat"], tc["lng"])
#         print("\n" + "*"*80)






import os
import sys
from dotenv import load_dotenv

# UTF-8 Fix for Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

load_dotenv()

from agents.graph import app_graph
from schemas.models import ServiceRequest, Location, UrgencyLevel

def run_test_case(title, query, location_name, lat, lng, urgency=UrgencyLevel.MEDIUM):
    print("\n" + "="*90)
    print(f"🚀 TEST CASE: {title}")
    print(f"💬 Query: \"{query}\"")
    print(f"📍 Location: {location_name}")
    print("="*90)

    request = ServiceRequest(
        user_id="test_user_123",
        raw_query=query,
        location=Location(address=location_name, lat=lat, lng=lng),
        urgency=urgency,
        language_detected="roman_urdu" if any(urdu in query.lower() for urdu in ["hai","chahiye","bhejien","karwani"]) else "en"
    )

    initial_state = {
        "request": request,
        "intent": None,
        "language": "en",
        "urgency": urgency.value if hasattr(urgency, 'value') else urgency,
        "providers": [],
        "selected_provider": None,
        "booking": None,
        "trace": [],
        "reasoning": "",
        "final_response": None
    }

    try:
        result = app_graph.invoke(initial_state)
        
        print("\n📜 AGENT TRACE:")
        for step in result.get("trace", []):
            print(f"   {step}")

        final = result.get("final_response", {})
        
        print("\n✨ FINAL OUTPUT:")
        print(f"Status     : {final.get('status', 'N/A')}")
        print(f"Message    : {final.get('message', '')[:120]}...")
        
        if "service_request" in final:
            sr = final["service_request"]
            print(f"Service    : {sr.get('type')} | Urgency: {sr.get('urgency')}")
        
        if "appointment" in final:
            ap = final["appointment"]
            print(f"Time       : {ap.get('scheduled_time')}")
            print(f"Booking ID : {ap.get('booking_id')}")
            if "reminder" in ap:
                print(f"Reminder   : {ap.get('reminder')}")
        
        if "recommendation" in final:
            rec = final["recommendation"]
            print(f"Provider   : {rec.get('provider_name')}")
            print(f"Rating     : {rec.get('rating')} | Distance: {rec.get('distance')}")
        
        if "next_steps" in final:
            print("\n📋 NEXT STEPS:")
            for i, step in enumerate(final["next_steps"], 1):
                print(f"  {i}. {step}")

    except Exception as e:
        print(f"\n💥 ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🛠️  ANTIGRAVITY SERVICE ORCHESTRATOR - FINAL TEST SUITE")
    print("Pakistan Informal Economy Services Testing\n")

    test_cases = [
        ("AC Technician (Roman Urdu)", 
         "Mera AC thanda nahi kar raha, gas check karwani hai. Jaldi bhejien.", 
         "North Nazimabad, Karachi", 24.9333, 67.0333),
        
        ("Home Tutor (Critical Test)", 
         "Bacha primary class mein hai, Maths aur Science parhanay k liye teacher chahiye Johar Town mein.", 
         "Johar Town, Lahore", 31.4697, 74.2728),
        
        ("Plumber Emergency", 
         "Kitchen sink leak ho raha hai bohot paani aa raha hai!", 
         "G-13, Islamabad", 33.6333, 72.9667),
        
        ("Beautician", 
         "Need a beautician for party makeup at home in F-6 Islamabad tomorrow.", 
         "F-6, Islamabad", 33.7297, 73.0747),
    ]

    for title, query, loc, lat, lng in test_cases:
        run_test_case(title, query, loc, lat, lng)
        print("\n" + "*" * 90)