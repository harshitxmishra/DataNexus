import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from backend.app.database import Base

class DimVendor(Base):
    """
    Vendor Dimension table.
    Grain: One row per unique business vendor.
    """
    __tablename__ = "dim_vendor"

    vendor_key = Column(Integer, primary_key=True, autoincrement=True)
    vendor_name = Column(String(255), nullable=False, unique=True, index=True)
    normalized_vendor_name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), default="General Services")
    country = Column(String(100), default="Unknown")
    first_seen_date = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoices = relationship("FactInvoice", back_populates="vendor")

class DimDate(Base):
    """
    Date Dimension table.
    Grain: One row per calendar date.
    Key format: YYYYMMDD (integer)
    """
    __tablename__ = "dim_date"

    date_key = Column(Integer, primary_key=True)  # e.g., 20261026
    full_date = Column(Date, nullable=False, unique=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    month_name = Column(String(20), nullable=False)
    week = Column(Integer, nullable=False)
    day_of_month = Column(Integer, nullable=False)
    day_name = Column(String(20), nullable=False)
    is_weekend = Column(Boolean, nullable=False)

    invoices_by_date = relationship("FactInvoice", foreign_keys="FactInvoice.invoice_date_key", back_populates="invoice_date_dim")
    invoices_by_due = relationship("FactInvoice", foreign_keys="FactInvoice.due_date_key", back_populates="due_date_dim")

class FactInvoice(Base):
    """
    Invoice Fact table.
    Grain: One row per verified invoice business record.
    Currencies are explicitly recorded; never aggregated across currencies without conversion.
    """
    __tablename__ = "fact_invoice"

    invoice_key = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    invoice_number = Column(String(100), nullable=False, index=True)
    
    vendor_key = Column(Integer, ForeignKey("dim_vendor.vendor_key"), nullable=False, index=True)
    invoice_date_key = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False, index=True)
    due_date_key = Column(Integer, ForeignKey("dim_date.date_key"), nullable=True, index=True)
    
    currency = Column(String(10), nullable=False, default="USD", index=True)
    subtotal = Column(Float, nullable=False, default=0.0)
    tax_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    
    payment_status = Column(String(50), nullable=False, default="Pending", index=True)  # Paid, Pending, Overdue, Disputed
    is_overdue = Column(Boolean, default=False, index=True)
    days_overdue = Column(Integer, default=0)
    
    extraction_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    vendor = relationship("DimVendor", back_populates="invoices")
    invoice_date_dim = relationship("DimDate", foreign_keys=[invoice_date_key], back_populates="invoices_by_date")
    due_date_dim = relationship("DimDate", foreign_keys=[due_date_key], back_populates="invoices_by_due")
    lines = relationship("FactInvoiceLine", back_populates="invoice", cascade="all, delete-orphan")

class FactInvoiceLine(Base):
    """
    Invoice Line Item Fact table.
    Grain: One row per extracted invoice line item.
    """
    __tablename__ = "fact_invoice_line"

    line_key = Column(Integer, primary_key=True, autoincrement=True)
    invoice_key = Column(Integer, ForeignKey("fact_invoice.invoice_key", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    description = Column(String(500), nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    unit_price = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("FactInvoice", back_populates="lines")

class FactDocumentProcessing(Base):
    """
    Document Processing Fact table.
    Grain: One row per document processing lifecycle attempt.
    """
    __tablename__ = "fact_document_processing"

    event_key = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    file_type = Column(String(100), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    ocr_invoked = Column(Boolean, default=False)
    indexing_succeeded = Column(Boolean, default=False)
    extraction_succeeded = Column(Boolean, default=False)
    final_status = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FactDataQuality(Base):
    """
    Data Quality Evaluation Fact table.
    Grain: One row per quality rule evaluation.
    """
    __tablename__ = "fact_data_quality"

    evaluation_key = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(100), nullable=False, index=True)
    rule_name = Column(String(150), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    severity = Column(String(50), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FactPipelineRun(Base):
    """
    Pipeline Execution Fact table.
    Grain: One row per ETL pipeline execution.
    """
    __tablename__ = "fact_pipeline_run"

    run_key = Column(Integer, primary_key=True, autoincrement=True)
    pipeline_name = Column(String(100), nullable=False, index=True)
    batch_id = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    rows_processed = Column(Integer, default=0)
    rows_rejected = Column(Integer, default=0)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
