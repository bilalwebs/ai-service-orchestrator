"""
DEPRECATED — Renamed to database_service.py.
This shim re-exports for backward compatibility.
Use:  from tools.database_service import db_service
"""
from tools.database_service import db_service as db_tool  # noqa: F401

__all__ = ["db_tool"]