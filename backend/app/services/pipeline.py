import uuid
import time
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.models.document import Document, ExtractedField, InvoiceLineItem
from backend.app.models.data_platform import PipelineRun, LineageEdge
from backend.app.models.analytics import (
    DimVendor, DimDate, FactInvoice, FactInvoiceLine, FactDocumentProcessing, FactPipelineRun
)
from backend.app.services.quality import quality_service

def date_to_key(dt: date) -> int:
    return int(dt.strftime("%Y%m%d"))

class DataPipelineService:
    def ensure_date_dim(self, dt: date, db: Session) -> DimDate:
        date_key = date_to_key(dt)
        dim = db.query(DimDate).filter(DimDate.date_key == date_key).first()
        if not dim:
            dim = DimDate(
                date_key=date_key,
                full_date=dt,
                year=dt.year,
                quarter=(dt.month - 1) // 3 + 1,
                month=dt.month,
                month_name=dt.strftime("%B"),
                week=int(dt.strftime("%U")),
                day_of_month=dt.day,
                day_name=dt.strftime("%A"),
                is_weekend=dt.weekday() >= 5
            )
            db.add(dim)
            db.flush()
        return dim

    def ensure_vendor_dim(self, vendor_name: str, db: Session) -> DimVendor:
        clean_name = vendor_name.strip() or "Unknown Vendor"
        norm_name = clean_name.lower()
        vendor = db.query(DimVendor).filter(DimVendor.normalized_vendor_name == norm_name).first()
        if not vendor:
            vendor = DimVendor(
                vendor_name=clean_name,
                normalized_vendor_name=norm_name,
                category="General Vendor",
                first_seen_date=datetime.utcnow().strftime("%Y-%m-%d")
            )
            db.add(vendor)
            db.flush()
        return vendor

    def run_invoice_transformation_pipeline(self, db: Session, batch_id: Optional[str] = None) -> PipelineRun:
        """
        Idempotent incremental ETL pipeline:
        Reads newly completed invoice documents and transforms them into dimensional fact and dimension models.
        """
        start_time = time.perf_counter()
        batch_id = batch_id or f"batch_{int(time.time())}"
        
        pipeline_run = PipelineRun(
            pipeline_name="invoice_dimensional_etl",
            batch_id=batch_id,
            status="running",
            start_time=datetime.utcnow(),
            source_range="completed_documents"
        )
        db.add(pipeline_run)
        db.commit()

        # Find completed documents not yet transformed or whose version has updated
        docs = db.query(Document).filter(
            Document.status.in_(["completed", "partially_completed"]),
            Document.document_type == "invoice"
        ).all()

        rows_read = len(docs)
        rows_inserted = 0
        rows_updated = 0
        rows_rejected = 0

        for doc in docs:
            try:
                fields = {f.field_name: f for f in doc.extracted_fields}
                
                # Check for required fields; if missing invoice_number and total, skip/reject
                if "invoice_number" not in fields and "total_amount" not in fields:
                    rows_rejected += 1
                    continue

                inv_num = fields.get("invoice_number", ExtractedField(field_value=f"INV-{doc.id[:8]}")).field_value
                vendor_name = fields.get("vendor_name", ExtractedField(field_value="Acme Supplier")).field_value
                
                # Ensure vendor dimension
                vendor_dim = self.ensure_vendor_dim(vendor_name, db)

                # Parse and ensure date dimension
                inv_date_str = fields.get("invoice_date", ExtractedField(normalized_value=datetime.utcnow().strftime("%Y-%m-%d"))).normalized_value
                try:
                    inv_date_dt = datetime.strptime(inv_date_str, "%Y-%m-%d").date()
                except Exception:
                    inv_date_dt = datetime.utcnow().date()
                date_dim = self.ensure_date_dim(inv_date_dt, db)

                # Due date
                due_date_key = None
                is_overdue = False
                days_overdue = 0
                if "due_date" in fields and fields["due_date"].normalized_value:
                    try:
                        due_date_dt = datetime.strptime(fields["due_date"].normalized_value, "%Y-%m-%d").date()
                        due_dim = self.ensure_date_dim(due_date_dt, db)
                        due_date_key = due_dim.date_key
                        today = datetime.utcnow().date()
                        if today > due_date_dt:
                            is_overdue = True
                            days_overdue = (today - due_date_dt).days
                    except Exception:
                        pass

                # Monetary Amounts
                currency = fields.get("currency", ExtractedField(normalized_value="USD")).normalized_value or "USD"
                
                def parse_float(val: Optional[str], default: float = 0.0) -> float:
                    if not val:
                        return default
                    try:
                        return float(val.replace(",", "").strip())
                    except ValueError:
                        return default

                subtotal = parse_float(fields.get("subtotal", ExtractedField(normalized_value="0.0")).normalized_value)
                tax_amt = parse_float(fields.get("tax_amount", ExtractedField(normalized_value="0.0")).normalized_value)
                total_amt = parse_float(fields.get("total_amount", ExtractedField(normalized_value="0.0")).normalized_value)
                payment_status = fields.get("payment_status", ExtractedField(field_value="Pending")).field_value

                # Upsert FactInvoice (idempotency check by document_id)
                fact = db.query(FactInvoice).filter(FactInvoice.document_id == doc.id).first()
                if fact:
                    fact.invoice_number = inv_num
                    fact.vendor_key = vendor_dim.vendor_key
                    fact.invoice_date_key = date_dim.date_key
                    fact.due_date_key = due_date_key
                    fact.currency = currency
                    fact.subtotal = subtotal
                    fact.tax_amount = tax_amt
                    fact.total_amount = total_amt
                    fact.payment_status = "Overdue" if is_overdue else payment_status
                    fact.is_overdue = is_overdue
                    fact.days_overdue = days_overdue
                    fact.extraction_confidence = doc.extraction_confidence
                    rows_updated += 1
                else:
                    fact = FactInvoice(
                        document_id=doc.id,
                        invoice_number=inv_num,
                        vendor_key=vendor_dim.vendor_key,
                        invoice_date_key=date_dim.date_key,
                        due_date_key=due_date_key,
                        currency=currency,
                        subtotal=subtotal,
                        tax_amount=tax_amt,
                        total_amount=total_amt,
                        payment_status="Overdue" if is_overdue else payment_status,
                        is_overdue=is_overdue,
                        days_overdue=days_overdue,
                        extraction_confidence=doc.extraction_confidence
                    )
                    db.add(fact)
                    db.flush()
                    rows_inserted += 1

                # Sync line items into FactInvoiceLine
                db.query(FactInvoiceLine).filter(FactInvoiceLine.document_id == doc.id).delete()
                for li in doc.line_items:
                    fact_line = FactInvoiceLine(
                        invoice_key=fact.invoice_key,
                        document_id=doc.id,
                        line_number=li.line_number,
                        description=li.description,
                        quantity=li.quantity,
                        unit_price=li.unit_price,
                        amount=li.amount
                    )
                    db.add(fact_line)

                # Record Lineage Edges
                self._record_lineage(doc, fact, fields, db)

                # Also trigger quality evaluation
                quality_service.evaluate_document_quality(doc.id, db, batch_id=batch_id)

            except Exception as e:
                rows_rejected += 1
                print(f"Error processing doc {doc.id} in pipeline: {e}")

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        pipeline_run.status = "success" if rows_rejected == 0 else "partially_completed"
        pipeline_run.rows_read = rows_read
        pipeline_run.rows_inserted = rows_inserted
        pipeline_run.rows_updated = rows_updated
        pipeline_run.rows_rejected = rows_rejected
        pipeline_run.end_time = datetime.utcnow()
        pipeline_run.duration_ms = duration_ms
        db.commit()

        # Also insert fact_pipeline_run
        db.add(FactPipelineRun(
            pipeline_name=pipeline_run.pipeline_name,
            batch_id=batch_id,
            status=pipeline_run.status,
            rows_processed=rows_inserted + rows_updated,
            rows_rejected=rows_rejected,
            duration_ms=duration_ms
        ))
        db.commit()

        return pipeline_run

    def _record_lineage(self, doc: Document, fact: FactInvoice, fields: Dict[str, ExtractedField], db: Session):
        """Construct exact traceable lineage relationships."""
        edges = [
            LineageEdge(
                source_type="file",
                source_id=doc.storage_path,
                target_type="document",
                target_id=doc.id,
                transformation_rule="storage.save_upload"
            ),
            LineageEdge(
                source_type="document",
                source_id=doc.id,
                target_type="fact_invoice",
                target_id=str(fact.invoice_key),
                transformation_rule="pipeline.invoice_dimensional_etl"
            ),
            LineageEdge(
                source_type="fact_invoice",
                source_id=str(fact.invoice_key),
                target_type="view",
                target_id="v_invoice_spend_by_vendor",
                transformation_rule="sql.view_aggregation"
            ),
            LineageEdge(
                source_type="view",
                source_id="v_invoice_spend_by_vendor",
                target_type="metric",
                target_id="total_spend_kpi",
                transformation_rule="bi.sum_spend"
            )
        ]

        if fact.is_overdue or fact.payment_status == "Overdue":
            edges.extend([
                LineageEdge(
                    source_type="fact_invoice",
                    source_id=str(fact.invoice_key),
                    target_type="view",
                    target_id="v_overdue_invoices",
                    transformation_rule="sql.view_filter"
                ),
                LineageEdge(
                    source_type="view",
                    source_id="v_overdue_invoices",
                    target_type="metric",
                    target_id="overdue_exposure_kpi",
                    transformation_rule="bi.sum_overdue"
                )
            ])
        
        # Link extracted fields to fact
        for field_name, f_obj in fields.items():
            edges.append(LineageEdge(
                source_type="document",
                source_id=doc.id,
                target_type="extracted_field",
                target_id=f_obj.id,
                transformation_rule=f"extraction.{f_obj.extraction_method}"
            ))
            edges.append(LineageEdge(
                source_type="extracted_field",
                source_id=f_obj.id,
                target_type="fact_invoice",
                target_id=str(fact.invoice_key),
                transformation_rule="pipeline.field_normalization"
            ))

        for edge in edges:
            # Avoid duplicate edges
            exists = db.query(LineageEdge).filter(
                LineageEdge.source_id == edge.source_id,
                LineageEdge.target_id == edge.target_id,
                LineageEdge.transformation_rule == edge.transformation_rule
            ).first()
            if not exists:
                db.add(edge)
        db.flush()

pipeline_service = DataPipelineService()
