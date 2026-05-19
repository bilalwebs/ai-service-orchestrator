import uuid

def generate_request_id() -> str:
    """Generate a short unique request identifier (8 hex characters)."""
    return uuid.uuid4().hex[:8]
