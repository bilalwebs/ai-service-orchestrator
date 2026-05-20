"""
db/data_seeder.py — Seeds the SQLite database with the initial 17 providers.

Run once after initializing your SQLite database:
    python -m db.data_seeder

Only inserts providers that do NOT already exist (idempotent).
Safe to import as a module — the guard only fires when run as __main__.
"""
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from schemas.models import ServiceType

# ── Seed data (mirrors mock_db.py) ───────────────────────────────────────────

PROVIDER_SEED_DATA: List[Dict[str, Any]] = [
    dict(id="p1",  name="Kamran Khan",   service_type=ServiceType.AC_TECHNICIAN, rating=4.7, address="North Nazimabad, Karachi",        lat=24.9333, lng=67.0333, phone="+923001234567", price_per_hour=1500.0, experience_years=8,  availability=True),
    dict(id="p2",  name="Zubair Ahmed",  service_type=ServiceType.PLUMBER,        rating=4.2, address="G-13, Islamabad",                 lat=33.6333, lng=72.9667, phone="+923007654321", price_per_hour=1000.0, experience_years=5,  availability=True),
    dict(id="p3",  name="Irfan Malik",   service_type=ServiceType.ELECTRICIAN,    rating=4.9, address="DHA Phase 5, Lahore",             lat=31.4697, lng=74.4098, phone="+923211112233", price_per_hour=1200.0, experience_years=12, availability=True),
    dict(id="p4",  name="Sajid Hussain", service_type=ServiceType.AC_TECHNICIAN,  rating=4.5, address="G-13/4, Islamabad",              lat=33.6350, lng=72.9700, phone="+923334445566", price_per_hour=1800.0, experience_years=6,  availability=True),
    dict(id="p5",  name="Babar Azam",    service_type=ServiceType.PLUMBER,        rating=3.8, address="Gulshan-e-Iqbal, Karachi",        lat=24.9167, lng=67.0833, phone="+923459998877", price_per_hour=800.0,  experience_years=3,  availability=True),
    dict(id="p6",  name="Asif Ali",      service_type=ServiceType.ELECTRICIAN,    rating=4.6, address="North Nazimabad Block H, Karachi", lat=24.9380, lng=67.0350, phone="+923008887766", price_per_hour=1100.0, experience_years=7,  availability=True),
    dict(id="p7",  name="Hamza Tariq",   service_type=ServiceType.TUTOR,          rating=5.0, address="Johar Town, Lahore",              lat=31.4697, lng=74.2728, phone="+923112223334", price_per_hour=2500.0, experience_years=4,  availability=True),
    dict(id="p8",  name="Noman Ijaz",    service_type=ServiceType.CLEANER,        rating=4.3, address="F-11, Islamabad",                 lat=33.6844, lng=72.9875, phone="+923335556667", price_per_hour=600.0,  experience_years=2,  availability=True),
    dict(id="p9",  name="Rizwan Khan",   service_type=ServiceType.PAINTER,        rating=4.1, address="Model Town, Lahore",              lat=31.4806, lng=74.3239, phone="+923451231231", price_per_hour=900.0,  experience_years=10, availability=True),
    dict(id="p10", name="Sania Mirza",   service_type=ServiceType.TUTOR,          rating=4.8, address="G-11, Islamabad",                 lat=33.6700, lng=72.9900, phone="+923214445556", price_per_hour=2200.0, experience_years=6,  availability=True),
    dict(id="p11", name="Farhan Saeed",  service_type=ServiceType.AC_TECHNICIAN,  rating=4.4, address="Gulberg III, Lahore",             lat=31.5100, lng=74.3400, phone="+923003334445", price_per_hour=1600.0, experience_years=5,  availability=True),
    dict(id="p12", name="Waseem Akram",  service_type=ServiceType.PLUMBER,        rating=4.9, address="Bahria Town, Karachi",            lat=24.9000, lng=67.2000, phone="+923337778889", price_per_hour=2000.0, experience_years=20, availability=True),
    dict(id="p13", name="Shoaib Malik",  service_type=ServiceType.ELECTRICIAN,    rating=4.0, address="Samanabad, Lahore",               lat=31.5333, lng=74.3000, phone="+923215556667", price_per_hour=950.0,  experience_years=4,  availability=True),
    dict(id="p14", name="Ayesha Omar",   service_type=ServiceType.CLEANER,        rating=4.7, address="DHA Phase 2, Islamabad",          lat=33.5333, lng=73.1333, phone="+923458889990", price_per_hour=750.0,  experience_years=3,  availability=True),
    dict(id="p15", name="Fawad Khan",    service_type=ServiceType.PAINTER,        rating=4.2, address="North Nazimabad Block L, Karachi", lat=24.9450, lng=67.0400, phone="+923116667778", price_per_hour=1300.0, experience_years=9,  availability=True),
    dict(id="p16", name="Zoya Ali",      service_type=ServiceType.BEAUTICIAN,     rating=4.9, address="F-6, Islamabad",                  lat=33.7297, lng=73.0747, phone="+923001112223", price_per_hour=3000.0, experience_years=7,  availability=True),
    dict(id="p17", name="Sara Khan",              service_type=ServiceType.BEAUTICIAN,    rating=4.6, address="Gulshan-e-Iqbal, Karachi",    lat=24.9167, lng=67.0833, phone="+923212223334", price_per_hour=2500.0, experience_years=5,  availability=True),
    # ── Islamabad-area providers (near default coords 33.6333, 72.9667) ──────
    dict(id="p18", name="Aslam Electric Works",  service_type=ServiceType.ELECTRICIAN,   rating=4.8, address="G-13/3, Islamabad",           lat=33.6380, lng=72.9720, phone="+923001234580", price_per_hour=1300.0, experience_years=10, availability=True),
    dict(id="p19", name="Naeem Electric Services",service_type=ServiceType.ELECTRICIAN,  rating=4.5, address="G-14, Islamabad",              lat=33.6510, lng=72.9830, phone="+923001234581", price_per_hour=1100.0, experience_years=7,  availability=True),
    dict(id="p20", name="Bilal Painters",         service_type=ServiceType.PAINTER,       rating=4.6, address="G-10, Islamabad",              lat=33.6600, lng=72.9960, phone="+923001234582", price_per_hour=950.0,  experience_years=8,  availability=True),
    dict(id="p21", name="Aqsa Beauty Salon",      service_type=ServiceType.BEAUTICIAN,    rating=4.9, address="G-13/2, Islamabad",            lat=33.6355, lng=72.9680, phone="+923001234583", price_per_hour=2800.0, experience_years=6,  availability=True),
    dict(id="p22", name="Tariq AC Repair",        service_type=ServiceType.AC_TECHNICIAN, rating=4.7, address="G-14/4, Islamabad",            lat=33.6470, lng=72.9760, phone="+923001234584", price_per_hour=1700.0, experience_years=9,  availability=True),
    dict(id="p23", name="Hassan Plumbing",        service_type=ServiceType.PLUMBER,       rating=4.6, address="G-13/1, Islamabad",            lat=33.6340, lng=72.9690, phone="+923001234585", price_per_hour=1100.0, experience_years=6,  availability=True),
    dict(id="p24", name="Clean Home Services",    service_type=ServiceType.CLEANER,       rating=4.5, address="G-13/4, Islamabad",            lat=33.6360, lng=72.9710, phone="+923001234586", price_per_hour=700.0,  experience_years=4,  availability=True),
    dict(id="p25", name="Ustad Tutor Academy",    service_type=ServiceType.TUTOR,         rating=4.9, address="G-13, Islamabad",              lat=33.6345, lng=72.9675, phone="+923001234587", price_per_hour=2000.0, experience_years=8,  availability=True),
]


def run_seed() -> None:
    """Insert all initial providers into the SQL database (idempotent)."""
    use_real_db = os.getenv("USE_REAL_DB", "false").lower() == "true"
    if not use_real_db:
        print("[data_seeder] USE_REAL_DB is not set to true. Seeder only runs against a real database.")
        print("[data_seeder] Set USE_REAL_DB=true in your .env and re-run.")
        return

    from db.database import SessionLocal, engine, Base
    from db import models as db_models
    import db.models  # ensure ORM classes are registered with Base

    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    inserted = 0
    skipped = 0
    try:
        for data in PROVIDER_SEED_DATA:
            existing = session.get(db_models.Provider, data["id"])
            if existing:
                skipped += 1
                continue
            row = db_models.Provider(**data)
            session.add(row)
            inserted += 1
        session.commit()
        print(f"[data_seeder] Done. Inserted: {inserted}, Skipped (already exist): {skipped}")
    except Exception as e:
        session.rollback()
        print(f"[data_seeder] ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_seed()
