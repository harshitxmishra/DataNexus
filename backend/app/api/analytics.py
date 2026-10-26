from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case
from backend.app.database import get_db
from backend.app.models.document import Document, DocumentChunk
from backend.app.models.data_platform import PipelineRun, DataQualityResult
from backend.app.models.analytics import (
    FactInvoice, DimVendor, DimDate, FactDocumentProcessing
)
from backend.app.schemas.analytics import (
    OverviewMetrics, VendorSpendItem, OverdueInvoiceItem, SpendTrendItem, ProcessingPerformanceMetric
)

router = APIRouter(prefix="/analytics", tags=["Business Intelligence & Analytics"])

@router.get("/overview", response_model=OverviewMetrics)
def get_overview_metrics(db: Session = Depends(get_db)):
    """Calculate operational and analytical overview KPIs from persisted database records."""
    total_docs = db.query(func.count(Document.id)).scalar() or 0
    completed_docs = db.query(func.count(Document.id)).filter(Document.status == "completed").scalar() or 0
    failed_docs = db.query(func.count(Document.id)).filter(Document.status == "failed").scalar() or 0
    backlog_docs = db.query(func.count(Document.id)).filter(Document.status.in_(["uploaded", "queued", "processing"])).scalar() or 0

    # Total spend in USD
    total_spend = db.query(func.sum(FactInvoice.total_amount)).filter(FactInvoice.currency == "USD").scalar() or 0.0

    # Average processing time ms
    avg_proc_time = db.query(func.avg(FactDocumentProcessing.processing_time_ms)).scalar() or 0.0

    # Quality Pass Rate
    total_evals = db.query(func.count(DataQualityResult.id)).scalar() or 0
    passed_evals = db.query(func.count(DataQualityResult.id)).filter(DataQualityResult.status == "pass").scalar() or 0
    quality_rate = round((passed_evals / total_evals * 100), 1) if total_evals > 0 else 100.0

    # Indexing Coverage Rate
    completed_count = completed_docs if completed_docs > 0 else total_docs
    docs_with_chunks = db.query(func.count(func.distinct(DocumentChunk.document_id))).filter(DocumentChunk.indexed_in_es == True).scalar() or 0
    indexing_rate = round((docs_with_chunks / completed_count * 100), 1) if completed_count > 0 else 100.0

    # Pipeline Runs & Active Vendors
    recent_runs = db.query(func.count(PipelineRun.id)).scalar() or 0
    active_vendors = db.query(func.count(DimVendor.vendor_key)).scalar() or 0

    return OverviewMetrics(
        total_documents=total_docs,
        completed_documents=completed_docs,
        processing_backlog=backlog_docs,
        failed_documents=failed_docs,
        total_spend_usd=round(float(total_spend), 2),
        avg_processing_time_ms=round(float(avg_proc_time), 1),
        data_quality_pass_rate=quality_rate,
        indexing_coverage_rate=indexing_rate,
        recent_pipeline_runs_count=recent_runs,
        active_vendors_count=active_vendors
    )

@router.get("/vendor-spend", response_model=List[VendorSpendItem])
def get_vendor_spend(db: Session = Depends(get_db)):
    """Aggregate spend by vendor and currency."""
    results = db.query(
        DimVendor.vendor_name,
        DimVendor.category,
        FactInvoice.currency,
        func.count(FactInvoice.invoice_key).label("inv_count"),
        func.sum(FactInvoice.subtotal).label("sum_subtotal"),
        func.sum(FactInvoice.tax_amount).label("sum_tax"),
        func.sum(FactInvoice.total_amount).label("sum_total"),
        func.avg(FactInvoice.extraction_confidence).label("avg_conf")
    ).join(
        FactInvoice, DimVendor.vendor_key == FactInvoice.vendor_key
    ).group_by(
        DimVendor.vendor_name, DimVendor.category, FactInvoice.currency
    ).order_by(
        desc("sum_total")
    ).all()

    items = []
    for r in results:
        items.append(VendorSpendItem(
            vendor_name=r[0],
            vendor_category=r[1] or "General",
            currency=r[2],
            invoice_count=r[3],
            total_subtotal=round(float(r[4] or 0), 2),
            total_tax=round(float(r[5] or 0), 2),
            total_spend=round(float(r[6] or 0), 2),
            avg_confidence=round(float(r[7] or 0.8), 3)
        ))
    return items

@router.get("/overdue-invoices", response_model=List[OverdueInvoiceItem])
def get_overdue_invoices(db: Session = Depends(get_db)):
    """List overdue invoices with days overdue and exposure."""
    results = db.query(
        FactInvoice, DimVendor, DimDate
    ).join(
        DimVendor, FactInvoice.vendor_key == DimVendor.vendor_key
    ).join(
        DimDate, FactInvoice.invoice_date_key == DimDate.date_key
    ).filter(
        (FactInvoice.is_overdue == True) | (FactInvoice.payment_status == "Overdue")
    ).order_by(
        desc(FactInvoice.days_overdue)
    ).all()

    items = []
    for fact, vendor, inv_date in results:
        due_str = None
        if fact.due_date_key:
            due_dim = db.query(DimDate).filter(DimDate.date_key == fact.due_date_key).first()
            if due_dim:
                due_str = due_dim.full_date.strftime("%Y-%m-%d")

        items.append(OverdueInvoiceItem(
            invoice_number=fact.invoice_number,
            vendor_name=vendor.vendor_name,
            currency=fact.currency,
            total_amount=fact.total_amount,
            payment_status=fact.payment_status,
            days_overdue=fact.days_overdue,
            invoice_date=inv_date.full_date.strftime("%Y-%m-%d"),
            due_date=due_str,
            document_id=fact.document_id
        ))
    return items

@router.get("/spend-trends", response_model=List[SpendTrendItem])
def get_spend_trends(db: Session = Depends(get_db)):
    """Monthly spend trends grouped by year-month and currency."""
    results = db.query(
        DimDate.year,
        DimDate.month,
        DimDate.month_name,
        FactInvoice.currency,
        func.count(FactInvoice.invoice_key).label("inv_count"),
        func.sum(FactInvoice.total_amount).label("sum_total")
    ).join(
        FactInvoice, DimDate.date_key == FactInvoice.invoice_date_key
    ).group_by(
        DimDate.year, DimDate.month, DimDate.month_name, FactInvoice.currency
    ).order_by(
        DimDate.year, DimDate.month
    ).all()

    items = []
    for r in results:
        period_label = f"{r[2][:3]} {r[0]}"
        items.append(SpendTrendItem(
            period=period_label,
            invoice_count=r[4],
            total_spend=round(float(r[5] or 0), 2),
            currency=r[3]
        ))
    return items

@router.get("/processing-performance", response_model=List[ProcessingPerformanceMetric])
def get_processing_performance(db: Session = Depends(get_db)):
    """Processing duration and success metrics grouped by file type."""
    results = db.query(
        FactDocumentProcessing.file_type,
        func.count(FactDocumentProcessing.event_key).label("total"),
        func.sum(case((FactDocumentProcessing.final_status == "completed", 1), else_=0)).label("success"),
        func.sum(case((FactDocumentProcessing.final_status == "failed", 1), else_=0)).label("failure"),
        func.avg(FactDocumentProcessing.processing_time_ms).label("avg_dur"),
        func.sum(case((FactDocumentProcessing.ocr_invoked == True, 1), else_=0)).label("ocr"),
        func.sum(case((FactDocumentProcessing.indexing_succeeded == True, 1), else_=0)).label("indexed")
    ).group_by(
        FactDocumentProcessing.file_type
    ).all()

    items = []
    for r in results:
        items.append(ProcessingPerformanceMetric(
            file_type=r[0],
            total_processed=r[1],
            success_count=int(r[2] or 0),
            failure_count=int(r[3] or 0),
            avg_duration_ms=round(float(r[4] or 0), 1),
            ocr_count=int(r[5] or 0),
            indexed_count=int(r[6] or 0)
        ))
    return items

@router.get("/duplicate-candidates")
def get_duplicate_candidates(db: Session = Depends(get_db)):
    """Identify duplicate documents and duplicate invoice candidate records."""
    docs = db.query(Document).filter(Document.is_duplicate == True).all()
    candidates = []
    for d in docs:
        candidates.append({
            "document_id": d.id,
            "filename": d.filename,
            "file_hash": d.file_hash,
            "duplicate_of_id": d.duplicate_of_id,
            "created_at": d.created_at.isoformat()
        })
    return {
        "total_duplicates_detected": len(candidates),
        "candidates": candidates
    }
