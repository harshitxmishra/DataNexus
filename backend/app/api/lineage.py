from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.schemas.data_platform import LineageGraphResponse, LineageSummaryResponse
from backend.app.services.lineage import lineage_service

router = APIRouter(prefix="/lineage", tags=["Lineage & Traceability"])

@router.get("/document/{document_id}", response_model=LineageGraphResponse)
def get_document_lineage(
    document_id: str,
    direction: str = Query("document", pattern="^(document|all|upstream|downstream)$", description="Lineage direction: document, all, upstream, or downstream"),
    max_depth: int = Query(6, ge=1, le=12, description="Maximum traversal depth (default: 6)"),
    db: Session = Depends(get_db)
):
    """
    Retrieve full multi-hop lineage graph for a document:
    file -> document -> extraction/chunk -> transformation -> fact -> view -> metric.
    """
    graph = lineage_service.get_document_lineage(
        document_id=document_id,
        db=db,
        direction=direction,
        max_depth=max_depth
    )
    return graph

@router.get("/node/{node_type}/{node_id}", response_model=LineageGraphResponse)
def get_node_lineage(
    node_type: str,
    node_id: str,
    direction: str = Query("all", pattern="^(all|upstream|downstream)$"),
    max_depth: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db)
):
    """
    Traverse multi-hop lineage rooted at any entity type
    (e.g. 'fact_invoice', 'extracted_field', 'view', 'metric', 'file').
    """
    graph = lineage_service.get_lineage_graph(
        root_id=node_id,
        root_type=node_type,
        db=db,
        direction=direction,
        max_depth=max_depth
    )
    return graph

@router.get("/summary", response_model=LineageSummaryResponse)
def get_lineage_summary(db: Session = Depends(get_db)):
    """Retrieve global lineage statistics, node counts by entity type, and transformation rule frequencies."""
    return lineage_service.get_lineage_summary(db)
