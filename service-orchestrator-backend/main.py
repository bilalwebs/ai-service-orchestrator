import os
from dotenv import load_dotenv

# Load environment variables before importing other modules
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import requests, admin
import uvicorn

app = FastAPI(
    title="Informal Service Orchestrator API",
    description="A multi-agent system for informal service booking in Pakistan.",
    version="1.0.0"
)

# CORS Middleware
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# CORS Middleware
# Development: allow all origins (*). For production or demo, set the ALLOWED_ORIGINS environment variable
# to a comma‑separated list of allowed origins, e.g. "https://myapp.vercel.app,http://localhost:3000"
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(requests.router)
app.include_router(admin.router)

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
