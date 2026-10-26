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
    """Inspect active search provider, cluster health, index status, and total indexed chunks."""
    return search_service.get_status(db)

@router.post("/reconcile")
def reconcile_search_index(prune_orphans: bool = False, db: Session = Depends(get_db)):
    """
    Compare canonical database document chunks with Elasticsearch index.
    Detects missing records (in DB but not in ES) and orphaned records (in ES but deleted from DB).
    Optionally prunes orphaned records when prune_orphans=True.
    """
    return search_service.reconcile(db, prune_orphans=prune_orphans)

@router.post("/reindex")
def reindex_all_documents(db: Session = Depends(get_db)):
    """
    Trigger bulk reindexing of all document chunks from the canonical database into Elasticsearch.
    """
    return search_service.reindex(db)

@router.post("/reembed")
def reembed_and_reindex_chunks(
    batch_size: int = 32,
    force_all: bool = False,
    db: Session = Depends(get_db)
):
    """
    Regenerate neural embeddings for existing chunks using the active pretrained model
    and update the search index. Safe, idempotent, and resumable.
    """
    return search_service.reembed_and_reindex(db, batch_size=batch_size, force_all=force_all)
