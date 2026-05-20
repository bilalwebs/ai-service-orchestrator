from typing import Any, Optional, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar('T')

class ErrorDetail(BaseModel):
    type: str
    details: Any

class APIResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None

def api_response(success: bool, message: str, data: Any = None, error: Any = None) -> dict:
    """
    Standardize the JSON response format across the entire API.
    Returns a dictionary suitable for FastAPI JSONResponse or standard endpoint return.
    """
    return {
        "success": success,
        "message": message,
        "data": data,
        "error": error
    }
