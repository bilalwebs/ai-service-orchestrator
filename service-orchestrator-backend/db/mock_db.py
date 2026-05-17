from typing import List, Dict
from schemas.models import Provider, ServiceType, Location, Booking

class MockDB:
    def __init__(self):
        self.providers: Dict[str, Provider] = {
            "p1": Provider(
                id="p1", name="Kamran Khan", service_type=ServiceType.AC_TECHNICIAN, 
                rating=4.7, location=Location(address="North Nazimabad, Karachi", lat=24.9333, lng=67.0333),
                phone="+923001234567", price_per_hour=1500.0, experience_years=8
            ),
            "p2": Provider(
                id="p2", name="Zubair Ahmed", service_type=ServiceType.PLUMBER, 
                rating=4.2, location=Location(address="G-13, Islamabad", lat=33.6333, lng=72.9667),
                phone="+923007654321", price_per_hour=1000.0, experience_years=5
            ),
            "p3": Provider(
                id="p3", name="Irfan Malik", service_type=ServiceType.ELECTRICIAN, 
                rating=4.9, location=Location(address="DHA Phase 5, Lahore", lat=31.4697, lng=74.4098),
                phone="+923211112233", price_per_hour=1200.0, experience_years=12
            ),
            "p4": Provider(
                id="p4", name="Sajid Hussain", service_type=ServiceType.AC_TECHNICIAN, 
                rating=4.5, location=Location(address="G-13/4, Islamabad", lat=33.6350, lng=72.9700),
                phone="+923334445566", price_per_hour=1800.0, experience_years=6
            ),
            "p5": Provider(
                id="p5", name="Babar Azam", service_type=ServiceType.PLUMBER, 
                rating=3.8, location=Location(address="Gulshan-e-Iqbal, Karachi", lat=24.9167, lng=67.0833),
                phone="+923459998877", price_per_hour=800.0, experience_years=3
            ),
            "p6": Provider(
                id="p6", name="Asif Ali", service_type=ServiceType.ELECTRICIAN, 
                rating=4.6, location=Location(address="North Nazimabad Block H, Karachi", lat=24.9380, lng=67.0350),
                phone="+923008887766", price_per_hour=1100.0, experience_years=7
            ),
            "p7": Provider(
                id="p7", name="Hamza Tariq", service_type=ServiceType.TUTOR, 
                rating=5.0, location=Location(address="Johar Town, Lahore", lat=31.4697, lng=74.2728),
                phone="+923112223334", price_per_hour=2500.0, experience_years=4
            ),
            "p8": Provider(
                id="p8", name="Noman Ijaz", service_type=ServiceType.CLEANER, 
                rating=4.3, location=Location(address="F-11, Islamabad", lat=33.6844, lng=72.9875),
                phone="+923335556667", price_per_hour=600.0, experience_years=2
            ),
            "p9": Provider(
                id="p9", name="Rizwan Khan", service_type=ServiceType.PAINTER, 
                rating=4.1, location=Location(address="Model Town, Lahore", lat=31.4806, lng=74.3239),
                phone="+923451231231", price_per_hour=900.0, experience_years=10
            ),
            "p10": Provider(
                id="p10", name="Sania Mirza", service_type=ServiceType.TUTOR, 
                rating=4.8, location=Location(address="G-11, Islamabad", lat=33.6700, lng=72.9900),
                phone="+923214445556", price_per_hour=2200.0, experience_years=6
            ),
            "p11": Provider(
                id="p11", name="Farhan Saeed", service_type=ServiceType.AC_TECHNICIAN, 
                rating=4.4, location=Location(address="Gulberg III, Lahore", lat=31.5100, lng=74.3400),
                phone="+923003334445", price_per_hour=1600.0, experience_years=5
            ),
            "p12": Provider(
                id="p12", name="Waseem Akram", service_type=ServiceType.PLUMBER, 
                rating=4.9, location=Location(address="Bahria Town, Karachi", lat=24.9000, lng=67.2000),
                phone="+923337778889", price_per_hour=2000.0, experience_years=20
            ),
            "p13": Provider(
                id="p13", name="Shoaib Malik", service_type=ServiceType.ELECTRICIAN, 
                rating=4.0, location=Location(address="Samanabad, Lahore", lat=31.5333, lng=74.3000),
                phone="+923215556667", price_per_hour=950.0, experience_years=4
            ),
            "p14": Provider(
                id="p14", name="Ayesha Omar", service_type=ServiceType.CLEANER, 
                rating=4.7, location=Location(address="DHA Phase 2, Islamabad", lat=33.5333, lng=73.1333),
                phone="+923458889990", price_per_hour=750.0, experience_years=3
            ),
            "p15": Provider(
                id="p15", name="Fawad Khan", service_type=ServiceType.PAINTER, 
                rating=4.2, location=Location(address="North Nazimabad Block L, Karachi", lat=24.9450, lng=67.0400),
                phone="+923116667778", price_per_hour=1300.0, experience_years=9
            ),
            "p16": Provider(
                id="p16", name="Zoya Ali", service_type=ServiceType.BEAUTICIAN, 
                rating=4.9, location=Location(address="F-6, Islamabad", lat=33.7297, lng=73.0747),
                phone="+923001112223", price_per_hour=3000.0, experience_years=7
            ),
            "p17": Provider(
                id="p17", name="Sara Khan", service_type=ServiceType.BEAUTICIAN, 
                rating=4.6, location=Location(address="Gulshan-e-Iqbal, Karachi", lat=24.9167, lng=67.0833),
                phone="+923212223334", price_per_hour=2500.0, experience_years=5
            ),
        }
        self.bookings: List[Booking] = []

    def get_providers_by_type(self, service_type: ServiceType) -> List[Provider]:
        return [p for p in self.providers.values() if p.service_type == service_type]

    def save_booking(self, booking: Booking):
        """Save booking - Consistent name used in graph.py"""
        self.bookings.append(booking)
        return booking

    def get_booking_by_id(self, booking_id: str) -> Booking | None:
        """Return a booking by its ID or None if not found."""
        for b in self.bookings:
            if b.id == booking_id:
                return b
        return None

    def get_all_bookings(self):
        return self.bookings


# Global instance
db = MockDB()