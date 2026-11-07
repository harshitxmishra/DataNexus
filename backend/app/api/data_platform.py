import io
import csv
import json
import time
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from backend.app.database import get_db
from backend.app.models.document import Document
from backend.app.models.data_platform import PipelineRun, DataQualityResult, RejectedRecord, StagedCsvRecord
from backend.app.models.analytics import FactInvoice, DimVendor, DimDate
from backend.app.schemas.data_platform import (
    PipelineRunResponse, DataQualityResultResponse, RejectedRecordResponse,
    DetailedScorecardResponse, QualityEvaluationTriggerResponse
)
from backend.app.services.pipeline import pipeline_service
from backend.app.services.quality import quality_service

router = APIRouter(prefix="/data-platform", tags=["Data Platform"])

@router.post("/pipeline/run", response_model=PipelineRunResponse)
def trigger_pipeline(db: Session = Depends(get_db)):
    """Trigger the incremental dimensional ETL pipeline."""
    run = pipeline_service.run_invoice_transformation_pipeline(db)
    return run

@router.get("/pipeline/runs", response_model=List[PipelineRunResponse])
def list_pipeline_runs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List historical ETL pipeline executions with metrics."""
    runs = db.query(PipelineRun).order_by(desc(PipelineRun.created_at)).offset(skip).limit(limit).all()
    return runs

@router.get("/quality/results", response_model=List[DataQualityResultResponse])
def list_quality_results(
    status: Optional[str] = Query(None, description="Filter: pass, fail, warning"),
    rule_category: Optional[str] = Query(None, description="Filter: completeness, consistency, etc."),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List persisted data quality rule evaluations."""
    query = db.query(DataQualityResult)
    if status:
        query = query.filter(DataQualityResult.status == status)
    if rule_category:
        query = query.filter(DataQualityResult.rule_category == rule_category)

    results = query.order_by(desc(DataQualityResult.evaluated_at)).offset(skip).limit(limit).all()
    return results

@router.get("/quality/scorecard", response_model=DetailedScorecardResponse)
def get_quality_scorecard(db: Session = Depends(get_db)):
    """Summary scorecard of rule pass/fail/warn metrics including by-rule and by-category breakdowns."""
    return quality_service.get_detailed_scorecard(db)

@router.post("/quality/evaluate", response_model=QualityEvaluationTriggerResponse)
def evaluate_quality(
    document_id: Optional[str] = Query(None, description="Optional document ID to evaluate; if omitted, evaluates all documents"),
    db: Session = Depends(get_db)
):
    """Trigger on-demand data quality rule evaluations for one or all completed documents."""
    if document_id:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")
        evals = quality_service.evaluate_document_quality(document_id, db)
        scorecard = quality_service.get_detailed_scorecard(db)
        return {
            "status": "success",
            "documents_evaluated": 1,
            "total_rules_evaluated": len(evals),
            "scorecard": scorecard
        }
    else:
        return quality_service.evaluate_all_documents(db)

@router.get("/rejected-records", response_model=List[RejectedRecordResponse])
def list_rejected_records(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """List rejected records with failure reasons."""
    recs = db.query(RejectedRecord).order_by(desc(RejectedRecord.created_at)).offset(skip).limit(limit).all()
    return recs

@router.post("/csv/ingest")
async def ingest_csv_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Ingest tabular CSV dataset.
    Inspects schema, validates columns, stages records, and records any malformed or rejected rows.
    """
    filename = file.filename or "dataset.csv"
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        text_content = content.decode("latin1")

    reader = csv.reader(io.StringIO(text_content))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty.")

    headers = [h.strip() for h in rows[0]]
    data_rows = rows[1:]
    batch_id = f"csv_{int(time.time())}"

    staged_count = 0
    rejected_count = 0

    for idx, row in enumerate(data_rows, start=1):
        if len(row) != len(headers):
            # Schema drift / column mismatch
            db.add(RejectedRecord(
                batch_id=batch_id,
                source_file=filename,
                row_index=idx,
                raw_data=",".join(row),
                rejection_reason=f"Column count mismatch: expected {len(headers)}, found {len(row)}."
            ))
            rejected_count += 1
            continue

        row_dict = dict(zip(headers, [val.strip() for val in row]))
        db.add(StagedCsvRecord(
            batch_id=batch_id,
            source_filename=filename,
            row_number=idx,
            data=json.dumps(row_dict),
            status="staged"
        ))
        staged_count += 1

    db.commit()

    return {
        "status": "success",
        "batch_id": batch_id,
        "filename": filename,
        "total_rows": len(data_rows),
        "staged_rows": staged_count,
        "rejected_rows": rejected_count,
        "columns": headers
    }

@router.get("/export/invoices")
def export_invoices_csv(db: Session = Depends(get_db)):
    """Stream curated analytical invoice dataset as CSV."""
    records = db.query(FactInvoice, DimVendor, DimDate).join(
        DimVendor, FactInvoice.vendor_key == DimVendor.vendor_key
    ).join(
        DimDate, FactInvoice.invoice_date_key == DimDate.date_key
    ).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "invoice_key", "invoice_number", "vendor_name", "vendor_category",
        "invoice_date", "currency", "subtotal", "tax_amount", "total_amount",
        "payment_status", "is_overdue", "days_overdue", "extraction_confidence"
    ])

    for fact, vendor, dt in records:
        writer.writerow([
            fact.invoice_key,
            fact.invoice_number,
            vendor.vendor_name,
            vendor.category,
            dt.full_date.strftime("%Y-%m-%d"),
            fact.currency,
            fact.subtotal,
            fact.tax_amount,
            fact.total_amount,
            fact.payment_status,
            fact.is_overdue,
            fact.days_overdue,
            fact.extraction_confidence
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=datanexus_invoices_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
    )
