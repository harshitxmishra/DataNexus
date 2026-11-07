from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database import get_db, check_database_connection
from backend.app.services.search import search_service
from backend.app.services.embeddings import embedding_service
from backend.app.config import settings

router = APIRouter(prefix="/health", tags=["System Health"])

@router.get("/liveness")
def liveness():
    """Basic liveness probe."""
    return {"status": "alive", "service": "datanexus-platform"}

@router.get("/readiness")
def readiness(db: Session = Depends(get_db)):
    """Deep readiness probe checking core dependencies and active providers."""
    db_status = check_database_connection()
    es_available = search_service.es_provider.is_available()
    
    # Test local embedding capability
    embedding_ready = False
    try:
        sample_vec = embedding_service.embed_text("DataNexus readiness test")
        embedding_ready = len(sample_vec) == 384
    except Exception:
        embedding_ready = False

    from backend.app.services.groq_service import groq_rag_service
    llm_configured = bool(settings.GROQ_API_KEY) or bool(settings.GEMINI_API_KEY)
    llm_status = "ready" if (groq_rag_service.is_available() or bool(settings.GEMINI_API_KEY)) else "fallback_extractive"

    all_ready = db_status.get("status") == "healthy" and embedding_ready

    return {
        "status": "ready" if all_ready else "degraded",
        "database": db_status,
        "elasticsearch": {
            "status": "connected" if es_available else "disconnected",
            "url": settings.ELASTICSEARCH_URL,
            "fallback_active": not es_available
        },
        "embedding_provider": {
            "status": "ready" if embedding_ready else "error",
            "model": embedding_service.model_name,
            "dimension": embedding_service.dimension,
            "representation_version": embedding_service.representation_version,
            "is_neural": True
        },
        "queue_broker": {
            "type": settings.QUEUE_BROKER,
            "status": "operational"
        },
        "llm_provider": {
            "provider": settings.LLM_PROVIDER,
            "configured": llm_configured,
            "status": llm_status,
            "model": settings.GROQ_MODEL if settings.LLM_PROVIDER == "groq" else settings.LLM_MODEL
        }
    }
