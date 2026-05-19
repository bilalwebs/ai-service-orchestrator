from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from db.database import Base
from schemas.models import ServiceType, BookingStatus

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    
    bookings = relationship("Booking", back_populates="user")

class Service(Base):
    __tablename__ = "services"
    id = Column(String, primary_key=True, index=True)
    name = Column(SQLEnum(ServiceType), unique=True, index=True)
    description = Column(String, nullable=True)

class Provider(Base):
    __tablename__ = "providers"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    service_type = Column(SQLEnum(ServiceType))
    rating = Column(Float)
    address = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    phone = Column(String)
    price_per_hour = Column(Float)
    experience_years = Column(Integer)
    availability = Column(Boolean, default=True)

    bookings = relationship("Booking", back_populates="provider")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    provider_id = Column(String, ForeignKey("providers.id"))
    service_type = Column(SQLEnum(ServiceType))
    status = Column(SQLEnum(BookingStatus), default=BookingStatus.CONFIRMED)
    scheduled_at = Column(DateTime)
    
    # Location data
    address = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    
    total_cost = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="bookings")
    provider = relationship("Provider", back_populates="bookings")

class AdminRequestLog(Base):
    __tablename__ = "admin_request_logs"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String)
    raw_query = Column(String)
    urgency = Column(String)
    intent = Column(String, nullable=True)
    language = Column(String, default="en")
    status = Column(String)
    booking_id = Column(String, nullable=True)
    trace = Column(JSON)
    created_at = Column(String)
