import os
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.database import get_db
from backend.app.models.document import Document
from backend.app.schemas.document import DocumentListItem, DocumentDetail
from backend.app.services.storage import storage_service
from backend.app.services.queue import queue_service

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentDetail)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("invoice"),
    process_immediately: bool = Form(True),
    db: Session = Depends(get_db)
):
    """
    Upload and register document.
    Validates file format, calculates SHA-256 hash, detects duplicates, safely stores original file,
    and runs the extraction and indexing lifecycle.
    """
    file_hash, storage_path, file_size, filename, detected_type = await storage_service.save_upload(file)

    # Duplicate detection by SHA-256 hash
    existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
    is_duplicate = existing_doc is not None
    duplicate_of_id = existing_doc.id if is_duplicate else None

    # Derive document type if csv
    if detected_type == "text/csv" or filename.lower().endswith(".csv"):
        document_type = "tabular_csv"

    doc = Document(
        filename=filename,
        original_name=file.filename or filename,
        file_type=detected_type,
        file_size=file_size,
        file_hash=file_hash,
        storage_path=storage_path,
        document_type=document_type,
        status="uploaded",
        is_duplicate=is_duplicate,
        duplicate_of_id=duplicate_of_id
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    if process_immediately:
        try:
            queue_service.execute_document_pipeline(doc.id, db)
            db.refresh(doc)
        except Exception as e:
            # Lifecycle sets status='failed'
            db.refresh(doc)

    return doc

@router.get("", response_model=List[DocumentListItem])
def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    search: Optional[str] = Query(None, description="Filter by filename"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List documents with filtering, sorting, and pagination."""
    query = db.query(Document)
    if status:
        query = query.filter(Document.status == status)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    if search:
        query = query.filter(Document.filename.ilike(f"%{search}%"))

    docs = query.order_by(desc(Document.created_at)).offset(skip).limit(limit).all()
    return docs

@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Retrieve complete document detail with page text, extracted fields, chunks, and stage history."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc

@router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    """Download original document binary file."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not os.path.isfile(doc.storage_path):
        raise HTTPException(status_code=404, detail="Document or physical file not found.")
    
    return FileResponse(
        path=doc.storage_path,
        filename=doc.original_name,
        media_type=doc.file_type
    )

@router.post("/{document_id}/reprocess", response_model=DocumentDetail)
def reprocess_document(document_id: str, db: Session = Depends(get_db)):
    """Idempotently re-run the full extraction, embedding, search indexing, and ETL pipeline."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    doc.version += 1
    db.commit()

    queue_service.execute_document_pipeline(document_id, db)
    db.refresh(doc)
    return doc

@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Safely delete document and propagate deletion to chunks, facts, and physical storage."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    storage_path = doc.storage_path
    db.delete(doc)
    db.commit()

    # Delete physical file
    storage_service.delete_file(storage_path)

    return {"status": "success", "message": f"Document {document_id} safely deleted."}
