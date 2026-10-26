from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.schemas.data_platform import LineageGraphResponse
from backend.app.services.lineage import lineage_service

router = APIRouter(prefix="/lineage", tags=["Lineage & Traceability"])

@router.get("/document/{document_id}", response_model=LineageGraphResponse)
def get_document_lineage(document_id: str, db: Session = Depends(get_db)):
    """
    Retrieve full multi-hop lineage graph for a document:
    file -> document -> extraction/chunk -> transformation -> fact -> view -> metric.
    """
    graph = lineage_service.get_document_lineage(document_id, db)
    return graph
