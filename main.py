import os
from dotenv import load_dotenv

# Load environment variables before importing other modules
load_dotenv()

from contextlib import asynccontextmanager
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import requests, admin
from routers.auth_router import router as auth_router
from fastapi.responses import JSONResponse
from routers import requests, admin, bookings, services
from schemas.response import api_response
import uvicorn

USE_REAL_DB = os.getenv("USE_REAL_DB", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if using real DB
    if USE_REAL_DB:
        from db.database import engine, Base
        import db.models  # ensure ORM models are registered
        Base.metadata.create_all(bind=engine)
        print("[startup] SQL database tables created / verified.")
    else:
        print("[startup] Using MockDB. Set USE_REAL_DB=true to switch to SQLite.")
    yield
    # Shutdown hooks can go here


app = FastAPI(
    title="Informal Service Orchestrator API",
    description="A multi-agent system for informal service booking in Pakistan.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)

# ── FIX 5: Global error handlers — consistent JSON error shape for all failures ──

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content=api_response(
            success=False,
            message="Resource not found",
            error={"type": "NotFoundError", "details": str(exc.detail) if hasattr(exc, "detail") else "Not found"}
        ),
    )

@app.exception_handler(405)
async def method_not_allowed_handler(request: Request, exc):
    return JSONResponse(
        status_code=405,
        content=api_response(
            success=False,
            message="Method not allowed",
            error={"type": "MethodNotAllowedError", "details": str(exc.detail) if hasattr(exc, "detail") else "Method not allowed"}
        ),
    )

@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content=api_response(
            success=False,
            message="Validation error",
            error={"type": "ValidationError", "details": exc.errors() if hasattr(exc, "errors") else str(exc)}
        ),
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    # Log the full traceback server-side; return a safe message to client
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content=api_response(
            success=False,
            message="Internal server error",
            error={"type": "InternalServerError", "details": "An unexpected error occurred. Please try again."}
        ),
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content=api_response(
            success=False,
            message="Unhandled exception",
            error={"type": "UnhandledException", "details": str(exc)}
        ),
    )

# ── CORS Middleware ───────────────────────────────────────────────────────────
# Development: allow all origins (*).
# For production, set ALLOWED_ORIGINS=https://myapp.vercel.app,http://localhost:3000
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(requests.router)
app.include_router(admin.router)
app.include_router(bookings.router)
app.include_router(services.router)


@app.get("/", tags=["Health"])
async def health_check():
    return api_response(
        success=True,
        message="System health check",
        data={
            "status": "online",
            "service": "Informal Service Orchestrator",
            "version": "1.0.0",
            "db_mode": "sqlite" if USE_REAL_DB else "mock",
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    # Note: Use reload=True only in development
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)