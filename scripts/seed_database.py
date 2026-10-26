#!/usr/bin/env python
"""
DataNexus Database Seeder Wrapper.
Generates realistic PDF invoice fixtures and initial dimensional data.
"""
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.seed import seed_database

if __name__ == "__main__":
    print("[DataNexus] Starting database seeding...")
    seed_database()
    print("[DataNexus] Database seeding complete.")
