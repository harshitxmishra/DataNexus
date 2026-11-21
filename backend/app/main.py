from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.analytics import router as analytics_router
from backend.app.api.data_platform import router as data_platform_router
from backend.app.api.documents import router as documents_router

# Import models to ensure registration with Base.metadata
# Import API routers
from backend.app.api.health import router as health_router
from backend.app.api.lineage import router as lineage_router
from backend.app.api.search import router as search_router
from backend.app.config import settings
from backend.app.database import Base, engine
from backend.app.models.views import init_analytical_views


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables and views exist
    Base.metadata.create_all(bind=engine)
    init_analytical_views(engine)

    # v2.0.0: Initialize OpenTelemetry tracing
    from backend.app.telemetry import setup_telemetry
    setup_telemetry(app)

    yield
    # Shutdown logic if any

app = FastAPI(
    title="DataNexus Platform API",
    description=(
        "Document Intelligence, Semantic Retrieval, Data Engineering, and Business Intelligence Platform.\n\n"
        "Enables end-to-end tracing from high-level BI dashboards and analytical SQL facts "
        "back through transformation pipelines to extracted fields, supporting page text, and original files."
    ),
    version="2.0.0",
    lifespan=lifespan
)

# CORS Configuration
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://fast-slate-b1xh91d.tmp.now",
    "https://datanexus.vercel.app",
    "https://datanexus-app.vercel.app",
]
if settings.FRONTEND_URL and settings.FRONTEND_URL not in allowed_origins:
    allowed_origins.append(settings.FRONTEND_URL)

if getattr(settings, "CORS_ORIGINS", ""):
    for o in settings.CORS_ORIGINS.split(","):
        trimmed = o.strip()
        if trimmed and trimmed not in allowed_origins:
            allowed_origins.append(trimmed)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://.*(\.vercel\.app|\.now|\.tmp\.now)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Cache-Control",
    ],
    expose_headers=[
        "Content-Disposition",
        "Content-Type",
        "Content-Length",
        "X-API-Key",
        "X-Accel-Buffering",
    ],
)

# Mount Routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(data_platform_router, prefix="/api")
app.include_router(lineage_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")

@app.get("/")
def root():
    return {
        "service": "DataNexus Document Intelligence & Analytics Platform",
        "version": "2.0.0",
        "status": "operational",
        "docs_url": "/docs"
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "DataNexus Platform",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
