# from pydantic import BaseModel, Field
# from typing import List, Optional
# from datetime import datetime
# from enum import Enum

# class ServiceType(str, Enum):
#     AC_TECHNICIAN = "ac_technician"
#     PLUMBER = "plumber"
#     ELECTRICIAN = "electrician"
#     TUTOR = "tutor"
#     CLEANER = "cleaner"
#     PAINTER = "painter"
#     BEAUTICIAN = "beautician"
#     OTHER = "other"

# class UrgencyLevel(str, Enum):
#     LOW = "low"
#     MEDIUM = "medium"
#     HIGH = "high"
#     EMERGENCY = "emergency"

# class BookingStatus(str, Enum):
#     PENDING = "pending"
#     CONFIRMED = "confirmed"
#     IN_PROGRESS = "in_progress"
#     COMPLETED = "completed"
#     CANCELLED = "cancelled"

# class Location(BaseModel):
#     address: str
#     lat: float
#     lng: float

# class ServiceRequest(BaseModel):
#     user_id: str
#     raw_query: str  # Original query (English/Urdu/Roman Urdu)
#     language_detected: Optional[str] = "en"
#     service_type: Optional[ServiceType] = None
#     location: Location
#     urgency: UrgencyLevel = UrgencyLevel.MEDIUM
#     preferred_time: Optional[datetime] = None
#     metadata: Optional[dict] = {}

# class Provider(BaseModel):
#     id: str
#     name: str
#     service_type: ServiceType
#     rating: float
#     location: Location
#     phone: str
#     price_per_hour: float
#     experience_years: int
#     availability: bool = True

# class Booking(BaseModel):
#     id: str
#     user_id: str
#     provider_id: str
#     service_type: ServiceType
#     status: BookingStatus = BookingStatus.PENDING
#     scheduled_at: datetime
#     location: Location
#     total_cost: Optional[float] = None
#     created_at: datetime = Field(default_factory=datetime.now)
#     updated_at: datetime = Field(default_factory=datetime.now)





from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ServiceType(str, Enum):
    AC_TECHNICIAN = "ac_technician"
    PLUMBER = "plumber"
    ELECTRICIAN = "electrician"
    TUTOR = "tutor"
    CLEANER = "cleaner"
    PAINTER = "painter"
    BEAUTICIAN = "beautician"
    OTHER = "other"


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Location(BaseModel):
    """User location details"""
    address: str = Field(..., description="Full address of the user")
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")


class ServiceRequest(BaseModel):
    """Main input model for service requests"""
    user_id: str = Field(..., description="Unique user identifier")
    raw_query: str = Field(..., description="Original natural language query (English/Roman Urdu/Urdu)")
    
    language_detected: Optional[str] = Field(default="en", description="Detected language")
    service_type: Optional[ServiceType] = Field(default=None, description="Pre-detected service type if available")
    
    location: Location = Field(..., description="User location")
    urgency: UrgencyLevel = Field(default=UrgencyLevel.MEDIUM, description="Urgency level of request")
    
    preferred_time: Optional[datetime] = Field(default=None, description="User preferred service time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class Provider(BaseModel):
    """Service provider details"""
    id: str
    name: str
    service_type: ServiceType
    rating: float = Field(..., ge=0, le=5)
    location: Location
    phone: str
    price_per_hour: float = Field(..., gt=0)
    experience_years: int = Field(..., ge=0)
    availability: bool = True


class Booking(BaseModel):
    """Booking record"""
    id: str
    user_id: str
    provider_id: str
    service_type: ServiceType
    
    status: BookingStatus = Field(default=BookingStatus.CONFIRMED)  # Changed to CONFIRMED for simulation
    scheduled_at: datetime
    location: Location
    total_cost: Optional[float] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# Optional: Config for better JSON handling
class Config:
    use_enum_values = True