import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from backend.app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    storage_path = Column(String(500), nullable=False)
    
    # State Machine: uploaded, queued, processing, partially_completed, completed, failed
    status = Column(String(50), nullable=False, default="uploaded", index=True)
    document_type = Column(String(50), nullable=False, default="invoice", index=True)
    
    page_count = Column(Integer, default=0)
    character_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    
    extraction_confidence = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    error_category = Column(String(100), nullable=True)
    version = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Relationships
    stage_events = relationship("DocumentStageEvent", back_populates="document", cascade="all, delete-orphan", order_by="DocumentStageEvent.created_at")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.chunk_index")
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")
    line_items = relationship("InvoiceLineItem", back_populates="document", cascade="all, delete-orphan", order_by="InvoiceLineItem.line_number")
    duplicates = relationship("Document", remote_side=[duplicate_of_id])

class DocumentStageEvent(Base):
    __tablename__ = "document_stage_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Stages: text_extraction, ocr, field_extraction, chunking, embedding, indexing, analytics_transform, quality_validation
    stage = Column(String(50), nullable=False)
    # Status: pending, running, completed, skipped, failed
    status = Column(String(50), nullable=False, default="pending")
    
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    retry_count = Column(Integer, default=0)
    details = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="stage_events")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=False, default=1)
    start_char = Column(Integer, nullable=False)
    end_char = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    
    # Embedding stored as serialized JSON array of floats for local search
    embedding = Column(Text, nullable=True)
    indexed_in_es = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")

class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # field_name: invoice_number, vendor_name, invoice_date, due_date, currency, subtotal, tax_amount, total_amount, payment_status
    field_name = Column(String(100), nullable=False, index=True)
    field_value = Column(String(500), nullable=False)
    normalized_value = Column(String(500), nullable=True)
    
    # Traceability & Provenance
    page_number = Column(Integer, nullable=False, default=1)
    supporting_text = Column(Text, nullable=True)
    start_char = Column(Integer, nullable=True)
    end_char = Column(Integer, nullable=True)
    
    confidence = Column(Float, nullable=True)
    extraction_method = Column(String(100), nullable=False, default="native_regex")
    validation_status = Column(String(50), nullable=False, default="valid")  # valid, warning, invalid
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="extracted_fields")

class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    description = Column(String(500), nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    page_number = Column(Integer, nullable=False, default=1)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="line_items")

class QueueJob(Base):
    """Durable database-backed background queue job table."""
    __tablename__ = "queue_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_type = Column(String(100), nullable=False, index=True)
    payload = Column(Text, nullable=False)  # JSON payload
    status = Column(String(50), nullable=False, default="queued", index=True)  # queued, running, completed, failed
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    locked_at = Column(DateTime, nullable=True)
    locked_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
