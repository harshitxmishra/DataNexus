import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Index
)
from backend.app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pipeline_name = Column(String(100), nullable=False, index=True)
    batch_id = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="running")  # running, success, failed, partially_completed
    
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    rows_read = Column(Integer, default=0)
    rows_inserted = Column(Integer, default=0)
    rows_updated = Column(Integer, default=0)
    rows_rejected = Column(Integer, default=0)
    
    source_range = Column(String(255), nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class DataQualityResult(Base):
    __tablename__ = "data_quality_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rule_name = Column(String(150), nullable=False, index=True)
    rule_category = Column(String(100), nullable=False)  # completeness, accuracy, uniqueness, consistency, referential_integrity
    evaluated_entity_type = Column(String(100), nullable=False)  # document, invoice, csv_row, pipeline_batch
    evaluated_entity_id = Column(String(100), nullable=False, index=True)
    
    status = Column(String(50), nullable=False)  # pass, fail, warning
    severity = Column(String(50), nullable=False, default="medium")  # critical, high, medium, low
    
    metric_value = Column(String(255), nullable=True)
    threshold = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, index=True)

class RejectedRecord(Base):
    __tablename__ = "rejected_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(100), nullable=False, index=True)
    source_file = Column(String(255), nullable=False)
    row_index = Column(Integer, nullable=False)
    raw_data = Column(Text, nullable=False)
    rejection_reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class LineageEdge(Base):
    """Lineage edge recording exact transformation relationships."""
    __tablename__ = "lineage_edges"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_type = Column(String(100), nullable=False)  # file, document, extraction, chunk, pipeline_run, fact_table
    source_id = Column(String(150), nullable=False, index=True)
    target_type = Column(String(100), nullable=False)  # document, chunk, extracted_field, fact_table, view, metric
    target_id = Column(String(150), nullable=False, index=True)
    transformation_rule = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class StagedCsvRecord(Base):
    """Raw staging layer for tabular CSV ingestion."""
    __tablename__ = "staged_csv_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    batch_id = Column(String(100), nullable=False, index=True)
    source_filename = Column(String(255), nullable=False)
    row_number = Column(Integer, nullable=False)
    data = Column(Text, nullable=False)  # JSON representation of raw row
    status = Column(String(50), nullable=False, default="staged")  # staged, transformed, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
