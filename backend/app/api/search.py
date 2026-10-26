from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.schemas.search import (
    SearchQueryRequest, SearchResponse, QARequest, QAResponse
)
from backend.app.services.search import search_service
from backend.app.services.qa import qa_service
from backend.app.models.document import DocumentChunk

router = APIRouter(prefix="/search", tags=["Search & Intelligence"])

@router.post("/query", response_model=SearchResponse)
def search_documents(payload: SearchQueryRequest, db: Session = Depends(get_db)):
    """
    Search indexed document chunks across full-text lexical, semantic dense vector, or hybrid RRF retrieval.
    Includes score inspection, page numbers, and text snippets.
    """
    result = search_service.search(
        query=payload.query,
        db=db,
        mode=payload.mode,
        top_k=payload.top_k,
        doc_type_filter=payload.document_type
    )
    return result

@router.post("/qa", response_model=QAResponse)
def answer_document_question(payload: QARequest, db: Session = Depends(get_db)):
    """
    Evidence-backed question answering over documents.
    Retrieves supporting context, verifies citations, and explicitly flags when evidence is insufficient.
    """
    result = qa_service.answer_question(
        question=payload.question,
        db=db,
        top_k=payload.top_k,
        doc_type_filter=payload.document_type
    )
    return result

@router.get("/status")
def get_search_engine_status(db: Session = Depends(get_db)):
    """Inspect active search provider, index status, and total indexed chunks."""
    provider, provider_name = search_service.get_active_provider()
    total_chunks = db.query(DocumentChunk).count()
    indexed_chunks = db.query(DocumentChunk).filter(DocumentChunk.indexed_in_es == True).count()

    return {
        "active_provider": provider_name,
        "elasticsearch_connected": search_service.es_provider.is_available(),
        "total_chunks_stored": total_chunks,
        "total_chunks_indexed": indexed_chunks,
        "supported_modes": ["lexical", "semantic", "hybrid"]
    }
