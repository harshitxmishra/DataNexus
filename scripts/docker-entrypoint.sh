#!/bin/bash
set -e

echo "=== DataNexus Backend Container Initializing ==="

# Wait for PostgreSQL if DATABASE_URL contains postgres
if [[ "$DATABASE_URL" == *"postgres"* ]]; then
  echo "Waiting for PostgreSQL database to be reachable..."
  python - <<'EOF'
import os
import sys
import time
from sqlalchemy import create_engine, text

db_url = os.environ.get("DATABASE_URL", "")
max_retries = 30
for i in range(max_retries):
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("PostgreSQL connection established successfully.")
        sys.exit(0)
    except Exception as e:
        print(f"Waiting for database... ({i+1}/{max_retries}) - {e}")
        time.sleep(2)
print("Database connection timed out.")
sys.exit(1)
EOF
fi

# Run Alembic migrations
echo "Applying Alembic database migrations..."
alembic upgrade head || {
  echo "Alembic upgrade encountered an issue, initializing base schema via SQLAlchemy..."
  python -c "from backend.app.database import init_db; init_db()"
}

# Auto-seed if database is empty
echo "Checking if database requires initial demonstration data..."
python - <<'EOF'
import os
from sqlalchemy import create_engine, text

db_url = os.environ.get("DATABASE_URL", "sqlite:///./datanexus.db")
try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
        if count == 0:
            print("Database has 0 documents. Running initial demonstration seed...")
            import subprocess
            subprocess.run(["python", "scripts/seed_database.py"], check=True)
        else:
            print(f"Database already populated with {count} documents.")
except Exception as e:
    print(f"Seed check skipped: {e}")
EOF

echo "Starting Uvicorn server on 0.0.0.0:8008..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8008 --workers 2
