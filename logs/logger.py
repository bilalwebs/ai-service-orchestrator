from pathlib import Path
import json
import threading
from datetime import datetime

# Determine logs directory relative to this file location
LOG_DIR = Path(__file__).resolve().parent
LOG_FILE = LOG_DIR / "agent_interactions.log"

# Ensure logs directory and file exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.touch(exist_ok=True)

_lock = threading.Lock()


def _write_log(entry: dict):
    """Write a JSON log entry to the agent_interactions.log file."""
    with _lock:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
            f.write("\n")


def log_interaction(request_id: str, stage: str, message: str, status: str = "info", **extra):
    """
    Log a structured interaction to agent_interactions.log.

    Args:
        request_id: Unique identifier for the request
        stage: Processing stage (e.g., "request_received", "intent_detection", "provider_discovery")
        message: Log message
        status: Status of the interaction (info, success, error, pending)
        **extra: Additional fields to include in the log entry
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": request_id,
        "stage": stage,
        "message": message,
        "status": status,
    }
    entry.update(extra)
    _write_log(entry)


def get_logger():
    """Return a logger instance for general use (optional)."""
    return _logger


class _Logger:
    def info(self, msg, **kwargs):
        _write_log({"level": "info", "message": msg, **kwargs})

    def error(self, msg, **kwargs):
        _write_log({"level": "error", "message": msg, **kwargs})

    def warning(self, msg, **kwargs):
        _write_log({"level": "warning", "message": msg, **kwargs})


_logger = _Logger()
