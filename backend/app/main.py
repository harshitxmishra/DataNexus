import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database import engine, Base
from backend.app.models.views import init_analytical_views

# Import models to ensure registration with Base.metadata
import backend.app.models

# Import API routers
from backend.app.api.health import router as health_router
from backend.app.api.documents import router as documents_router
from backend.app.api.search import router as search_router
from backend.app.api.data_platform import router as data_platform_router
from backend.app.api.lineage import router as lineage_router
from backend.app.api.analytics import router as analytics_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables and views exist
    Base.metadata.create_all(bind=engine)
    init_analytical_views(engine)
    yield
    # Shutdown logic if any

app = FastAPI(
    title="DataNexus Platform API",
    description=(
        "Document Intelligence, Semantic Retrieval, Data Engineering, and Business Intelligence Platform.\n\n"
        "Enables end-to-end tracing from high-level BI dashboards and analytical SQL facts "
        "back through transformation pipelines to extracted fields, supporting page text, and original files."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "version": "1.0.0",
        "status": "operational",
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
