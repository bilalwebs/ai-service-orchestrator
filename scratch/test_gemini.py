import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()

def test_model(model_name):
    print(f"Testing model: {model_name}")
    try:
        llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=os.getenv("GOOGLE_API_KEY"))
        response = llm.invoke([HumanMessage(content="Hi")])
        print(f"Success! Response: {response.content}")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

models_to_try = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-flash-preview", "gemini-3.1-flash-lite"]
for m in models_to_try:
    if test_model(m):
        print(f"RECOMMENDED MODEL: {m}")
        break
