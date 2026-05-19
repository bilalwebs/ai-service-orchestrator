# Configuration constants for Antigravity Service Orchestrator

# Maximum distance (km) a provider can be from the user to be considered
MAX_DISTANCE_KM: float = 10.0

# Number of top providers to return in the recommendation list
TOP_N_PROVIDERS: int = 3

# Scoring weights – can be tuned for production
WEIGHT_RATING: float = 3.0
WEIGHT_DISTANCE: float = 1.0  # will be multiplied by urgency factor later
WEIGHT_EXPERIENCE: float = 0.2

# Urgency distance multiplier – higher urgency favours closer providers
URGENCY_DISTANCE_MULTIPLIER = {
    "high": 2.0,
    "emergency": 3.0,
    "medium": 1.0,
    "low": 0.5,
}
