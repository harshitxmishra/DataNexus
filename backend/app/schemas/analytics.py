from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class OverviewMetrics(BaseModel):
    total_documents: int
    completed_documents: int
    processing_backlog: int
    failed_documents: int
    total_spend_usd: float
    avg_processing_time_ms: float
    data_quality_pass_rate: float
    indexing_coverage_rate: float
    recent_pipeline_runs_count: int
    active_vendors_count: int

class VendorSpendItem(BaseModel):
    vendor_name: str
    vendor_category: str
    currency: str
    invoice_count: int
    total_subtotal: float
    total_tax: float
    total_spend: float
    avg_confidence: float

class OverdueInvoiceItem(BaseModel):
    invoice_number: str
    vendor_name: str
    currency: str
    total_amount: float
    payment_status: str
    days_overdue: int
    invoice_date: str
    due_date: Optional[str] = None
    document_id: str

class SpendTrendItem(BaseModel):
    period: str
    invoice_count: int
    total_spend: float
    currency: str

class ProcessingPerformanceMetric(BaseModel):
    file_type: str
    total_processed: int
    success_count: int
    failure_count: int
    avg_duration_ms: float
    ocr_count: int
    indexed_count: int
