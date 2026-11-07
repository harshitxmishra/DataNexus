from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case, text
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

# Curated Analytical SQL Views & Power BI Semantic Model Endpoints (Phase 5)

ALLOWED_CURATED_VIEWS = {
    "v_daily_ingestion": {
        "description": "Daily ingestion velocity, document throughput, byte volume, and duplicate rates",
        "domain": "Operational Ingestion",
        "columns": ["ingestion_date", "total_documents", "total_bytes", "avg_page_count", "duplicate_count"]
    },
    "v_processing_performance": {
        "description": "Pipeline processing latency, OCR invocation, indexing, and success/failure counts by file type",
        "domain": "Processing Diagnostics",
        "columns": ["file_type", "total_processed", "success_count", "failure_count", "avg_duration_ms", "ocr_count", "indexed_count"]
    },
    "v_invoice_spend_by_vendor": {
        "description": "Curated invoice spend, subtotal, tax, and extraction confidence aggregated by vendor and currency",
        "domain": "Accounts Payable & Procurement",
        "columns": ["vendor_name", "vendor_category", "currency", "invoice_count", "total_subtotal", "total_tax", "total_spend", "avg_confidence"]
    },
    "v_overdue_invoices": {
        "description": "Active overdue invoice liabilities, vendor names, exposure amounts, and days overdue",
        "domain": "Financial Risk & Treasury",
        "columns": ["invoice_number", "vendor_name", "currency", "total_amount", "payment_status", "days_overdue", "invoice_date", "due_date", "document_id"]
    },
    "v_data_quality_scorecard": {
        "description": "Evaluation totals, pass/warn/fail breakdowns, and pass percentages grouped by rule and category",
        "domain": "Data Governance",
        "columns": ["rule_name", "rule_category", "total_evaluations", "passed_count", "failed_count", "warning_count", "pass_percentage"]
    },
    "v_pipeline_freshness": {
        "description": "ETL batch freshness, execution counts, row throughput, and rejected row counts by pipeline",
        "domain": "Data Platform Operations",
        "columns": ["pipeline_name", "total_runs", "last_run_at", "total_rows_read", "total_rows_processed", "total_rows_rejected", "successful_runs"]
    },
    "v_indexing_coverage": {
        "description": "Search index coverage percentage comparing completed documents with Elasticsearch indexed chunks",
        "domain": "Search Infrastructure",
        "columns": ["total_documents", "completed_documents", "indexed_documents", "total_chunks_indexed", "coverage_percentage"]
    }
}

@router.get("/views")
def list_analytical_views(db: Session = Depends(get_db)):
    """List all available curated analytical SQL views with descriptions, target domains, and live row counts."""
    view_catalog = []
    for view_name, meta in ALLOWED_CURATED_VIEWS.items():
        row_count = 0
        try:
            row_count = db.execute(text(f"SELECT COUNT(*) FROM {view_name}")).scalar() or 0
        except Exception:
            pass
        view_catalog.append({
            "view_name": view_name,
            "description": meta["description"],
            "domain": meta["domain"],
            "columns": meta["columns"],
            "row_count": row_count
        })
    return {"views": view_catalog}

@router.get("/views/{view_name}")
def query_analytical_view(
    view_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Query rows from a curated analytical SQL view with pagination.
    Strictly validates view_name against the allowed analytical views whitelist to prevent SQL injection.
    """
    if view_name not in ALLOWED_CURATED_VIEWS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid view name '{view_name}'. Allowed curated views: {list(ALLOWED_CURATED_VIEWS.keys())}"
        )

    meta = ALLOWED_CURATED_VIEWS[view_name]
    try:
        total_count = db.execute(text(f"SELECT COUNT(*) FROM {view_name}")).scalar() or 0
        result = db.execute(text(f"SELECT * FROM {view_name} LIMIT :limit OFFSET :skip"), {"limit": limit, "skip": skip})
        columns = list(result.keys()) if result.keys() else meta["columns"]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return {
            "view_name": view_name,
            "description": meta["description"],
            "domain": meta["domain"],
            "total_rows": total_count,
            "returned_rows": len(rows),
            "skip": skip,
            "limit": limit,
            "columns": columns,
            "data": rows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query view '{view_name}': {str(e)}")

@router.get("/powerbi/semantic-model")
def get_powerbi_semantic_model():
    """
    Retrieve complete Power BI / Analysis Services semantic model definition:
    dimensional star schema, table cardinalities, DAX measure catalog, and connection templates.
    """
    return {
        "dataset_name": "DataNexus Document Intelligence & Enterprise Semantic Model",
        "architecture": "Kimball Dimensional Star Schema with Curated SQL Views",
        "recommended_connectivity_mode": "DirectQuery or Import",
        "tables": [
            {
                "name": "dim_vendor",
                "type": "Dimension",
                "description": "Vendor master dimension with clean normalized naming and categorization",
                "primary_key": "vendor_key",
                "columns": ["vendor_key", "vendor_name", "normalized_vendor_name", "category", "first_seen_date"]
            },
            {
                "name": "dim_date",
                "type": "Dimension",
                "description": "Standard calendar date dimension covering invoice and due dates",
                "primary_key": "date_key",
                "columns": ["date_key", "full_date", "year", "quarter", "month", "month_name", "week", "day_of_month", "day_name", "is_weekend"]
            },
            {
                "name": "fact_invoice",
                "type": "Fact",
                "description": "Grain: One row per processed commercial invoice with spend, tax, and status metrics",
                "primary_key": "invoice_key",
                "columns": ["invoice_key", "document_id", "invoice_number", "vendor_key", "invoice_date_key", "due_date_key", "currency", "subtotal", "tax_amount", "total_amount", "payment_status", "is_overdue", "days_overdue", "extraction_confidence"]
            },
            {
                "name": "fact_invoice_line",
                "type": "Fact (Detail)",
                "description": "Grain: One row per individual itemized line on an invoice",
                "primary_key": "line_key",
                "columns": ["line_key", "invoice_key", "document_id", "line_number", "description", "quantity", "unit_price", "amount"]
            },
            {
                "name": "fact_document_processing",
                "type": "Fact (Telemetry)",
                "description": "Grain: One row per document processing lifecycle attempt",
                "primary_key": "event_key",
                "columns": ["event_key", "document_id", "file_type", "processing_time_ms", "ocr_invoked", "indexing_succeeded", "final_status"]
            },
            {
                "name": "fact_pipeline_run",
                "type": "Fact (ETL)",
                "description": "Grain: One row per dimensional ETL execution batch",
                "primary_key": "run_key",
                "columns": ["run_key", "pipeline_name", "batch_id", "status", "rows_processed", "rows_rejected", "duration_ms"]
            }
        ],
        "relationships": [
            {
                "from_table": "fact_invoice",
                "from_column": "vendor_key",
                "to_table": "dim_vendor",
                "to_column": "vendor_key",
                "cardinality": "ManyToOne",
                "cross_filter_direction": "Single",
                "is_active": True,
                "description": "Links invoices to vendor dimension"
            },
            {
                "from_table": "fact_invoice",
                "from_column": "invoice_date_key",
                "to_table": "dim_date",
                "to_column": "date_key",
                "cardinality": "ManyToOne",
                "cross_filter_direction": "Single",
                "is_active": True,
                "description": "Primary active date relationship: invoice date"
            },
            {
                "from_table": "fact_invoice",
                "from_column": "due_date_key",
                "to_table": "dim_date",
                "to_column": "date_key",
                "cardinality": "ManyToOne",
                "cross_filter_direction": "Single",
                "is_active": False,
                "description": "Secondary inactive date relationship: payment due date (use USERELATIONSHIP)"
            },
            {
                "from_table": "fact_invoice_line",
                "from_column": "invoice_key",
                "to_table": "fact_invoice",
                "to_column": "invoice_key",
                "cardinality": "ManyToOne",
                "cross_filter_direction": "Single",
                "is_active": True,
                "description": "Links itemized lines to header fact invoice"
            }
        ],
        "dax_measures": [
            {
                "name": "Total Invoiced Spend USD",
                "display_folder": "Spend Metrics",
                "expression": "CALCULATE(SUM(fact_invoice[total_amount]), fact_invoice[currency] = \"USD\")",
                "format_string": "$#,##0.00",
                "description": "Sum of total invoiced amounts normalized to USD"
            },
            {
                "name": "Total Invoiced Tax USD",
                "display_folder": "Spend Metrics",
                "expression": "CALCULATE(SUM(fact_invoice[tax_amount]), fact_invoice[currency] = \"USD\")",
                "format_string": "$#,##0.00",
                "description": "Total sales tax recorded across USD invoices"
            },
            {
                "name": "Overdue Liability Exposure",
                "display_folder": "Risk & Overdue",
                "expression": "CALCULATE(SUM(fact_invoice[total_amount]), fact_invoice[is_overdue] = TRUE())",
                "format_string": "$#,##0.00",
                "description": "Total dollar value of invoices past their due date"
            },
            {
                "name": "Overdue Invoices Count",
                "display_folder": "Risk & Overdue",
                "expression": "CALCULATE(COUNTROWS(fact_invoice), fact_invoice[is_overdue] = TRUE())",
                "format_string": "#,##0",
                "description": "Total count of invoices marked as overdue"
            },
            {
                "name": "Overdue Rate %",
                "display_folder": "Risk & Overdue",
                "expression": "DIVIDE([Overdue Invoices Count], COUNTROWS(fact_invoice), 0) * 100",
                "format_string": "0.0%",
                "description": "Percentage of total invoices that are overdue"
            },
            {
                "name": "Data Quality Pass Rate %",
                "display_folder": "Data Governance",
                "expression": "AVERAGE(v_data_quality_scorecard[pass_percentage])",
                "format_string": "0.0%",
                "description": "Average rule compliance pass rate across all evaluated entities"
            },
            {
                "name": "Average Processing Time Seconds",
                "display_folder": "Operational Telemetry",
                "expression": "DIVIDE(AVERAGE(fact_document_processing[processing_time_ms]), 1000)",
                "format_string": "0.0s",
                "description": "Mean document ingestion and extraction pipeline latency in seconds"
            },
            {
                "name": "Invoice Line Items Count",
                "display_folder": "Line Item Analytics",
                "expression": "COUNTROWS(fact_invoice_line)",
                "format_string": "#,##0",
                "description": "Total number of extracted and staged line item records"
            }
        ],
        "curated_views": list(ALLOWED_CURATED_VIEWS.keys()),
        "connection_parameters": {
            "server": "localhost:5432",
            "database": "datanexus",
            "schema": "public",
            "authentication": "Database Credentials"
        }
    }
