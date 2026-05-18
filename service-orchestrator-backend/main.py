import os
from dotenv import load_dotenv

# Load environment variables before importing other modules
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import requests
from routers.auth_router import router as auth_router
import uvicorn

app = FastAPI(
    title="Informal Service Orchestrator API",
    description="A multi-agent system for informal service booking in Pakistan.",
    version="1.0.0"
)

app.include_router(auth_router)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(requests.router)

@app.get("/")
async def health_check():
    return {
        "status": "online",
        "service": "Informal Service Orchestrator",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # Note: Use reload=True only in development
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
