"""
DEPRECATED — Renamed to data_seeder.py.
This shim exists for backward compatibility.
Use:  python -m db.data_seeder
"""
from db.data_seeder import run_seed

if __name__ == "__main__":
    run_seed()
