# pyrefly: ignore [missing-import]
import googlemaps
import os
import logging
from typing import List, Dict
from math import radians, cos, sin, asin, sqrt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MapsTool:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.gmaps = None
        
        # Check if API key is missing or is a placeholder
        if not self.api_key or "your_" in self.api_key or self.api_key == "":
            logger.warning("GOOGLE_MAPS_API_KEY is missing or invalid. Using mock/fallback calculations.")
            return

        try:
            self.gmaps = googlemaps.Client(key=self.api_key)
            # Simple test to see if key is valid (optional, but good for early failure)
            logger.info("Google Maps client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Google Maps client: {str(e)}. Falling back to mock calculations.")
            self.gmaps = None

    def get_distance(self, lat1, lng1, lat2, lng2):
        """Calculate the great circle distance in kilometers between two points using Haversine formula."""
        # We use Haversine as the primary/fallback distance tool for performance
        # since we don't necessarily need Google's Matrix API for simple proximity
        R = 6371  # Radius of earth in kilometers
        dLat = radians(lat2 - lat1)
        dLon = radians(lng2 - lng1)
        lat1 = radians(lat1)
        lat2 = radians(lat2)

        a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
        c = 2*asin(sqrt(a))
        distance = R * c
        return distance

    def geocode(self, address: str):
        """Convert address to lat/lng using Google Maps or a fallback."""
        if not self.gmaps:
            logger.warning(f"Geocoding '{address}' using fallback coordinates.")
            # Smarter fallback based on address details
            addr_lower = address.lower()
            if any(kw in addr_lower for kw in ["islamabad", "g-13", "g-14", "f-11", "f-6", "g-11"]):
                return {"lat": 33.6844, "lng": 73.0479}
            elif any(kw in addr_lower for kw in ["lahore", "gulberg", "johar town", "model town"]):
                return {"lat": 31.5204, "lng": 74.3587}
            return {"lat": 24.8607, "lng": 67.0011} 
        
        try:
            result = self.gmaps.geocode(address)
            if result:
                return result[0]['geometry']['location']
        except Exception as e:
            logger.error(f"Geocoding error: {str(e)}")
            
        # Smarter fallback here as well in case of API failure
        addr_lower = address.lower()
        if any(kw in addr_lower for kw in ["islamabad", "g-13", "g-14", "f-11", "f-6", "g-11"]):
            return {"lat": 33.6844, "lng": 73.0479}
        elif any(kw in addr_lower for kw in ["lahore", "gulberg", "johar town", "model town"]):
            return {"lat": 31.5204, "lng": 74.3587}
        return {"lat": 24.8607, "lng": 67.0011} 

maps_tool = MapsTool()
