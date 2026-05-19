from fastapi import APIRouter
from tools.database_service import db_service
from schemas.models import ServiceType
from schemas.response import api_response

router = APIRouter(prefix="/services", tags=["Services"])

@router.get("/")
async def list_services():
    """Returns an initial catalog of available services."""
    services = [{"id": s.name, "value": s.value, "label": s.value.replace("_", " ").title()} for s in ServiceType]
    return api_response(success=True, message="Services retrieved successfully", data=services)

@router.get("/providers")
async def list_providers():
    """Returns all available providers."""
    providers = [p.model_dump() for p in db_service.get_all_providers()]
    return api_response(success=True, message="Providers retrieved successfully", data=providers)

