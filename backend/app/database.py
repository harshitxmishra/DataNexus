import time
from typing import Generator, Dict, Any
from urllib.parse import urlparse
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from backend.app.config import settings

def normalize_database_url(url: str) -> str:
    """Normalize database URL to ensure appropriate dialect and driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url

db_url = normalize_database_url(settings.DATABASE_URL)
is_sqlite = db_url.startswith("sqlite")
is_postgres = db_url.startswith("postgresql")

if is_sqlite:
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=False
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL configuration with robust connection pooling
    engine = create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining transactional database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def mask_database_url(url: str) -> str:
    """Safely mask username and password credentials from database URLs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme.startswith("sqlite"):
            return "sqlite_local"
        netloc = parsed.netloc
        if "@" in netloc:
            creds, host_port = netloc.split("@", 1)
            username = creds.split(":", 1)[0]
            masked_netloc = f"{username}:***@{host_port}"
        else:
            masked_netloc = netloc
        return f"{parsed.scheme}://{masked_netloc}{parsed.path}"
    except Exception:
        return "masked_connection_url"

def check_database_connection() -> Dict[str, Any]:
    """Inspect database connectivity, dialect, and query latency."""
    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "healthy",
            "dialect": engine.dialect.name,
            "latency_ms": latency_ms,
            "url_masked": mask_database_url(settings.DATABASE_URL)
        }
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "status": "unhealthy",
            "dialect": engine.dialect.name if hasattr(engine, "dialect") else "unknown",
            "latency_ms": latency_ms,
            "error": str(e)
        }
