from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.document import Document, ExtractedField, DocumentChunk
from backend.app.models.data_platform import DataQualityResult
from backend.app.models.analytics import FactInvoice, DimVendor

STANDARD_CURRENCIES = {"USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "CHF", "CNY"}

class DataQualityService:
    def evaluate_document_quality(self, document_id: str, db: Session, batch_id: Optional[str] = None) -> List[DataQualityResult]:
        """Evaluate comprehensive deterministic quality rules for a processed document."""
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return []

        evaluations: List[DataQualityResult] = []
        eval_time = datetime.utcnow()
        fields = {f.field_name: f for f in doc.extracted_fields}

        # 1. Required Fields Completeness
        required_fields = ["invoice_number", "vendor_name", "total_amount", "invoice_date"]
        missing_fields = [rf for rf in required_fields if rf not in fields or not fields[rf].field_value]
        evaluations.append(DataQualityResult(
            rule_name="REQUIRED_FIELDS_COMPLETENESS",
            rule_category="completeness",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="pass" if not missing_fields else "fail",
            severity="critical",
            metric_value=f"{len(required_fields) - len(missing_fields)}/{len(required_fields)}",
            threshold="4/4",
            details="All mandatory invoice fields present." if not missing_fields else f"Missing fields: {', '.join(missing_fields)}",
            evaluated_at=eval_time
        ))

        # 2. Valid Currency Code
        curr_field = fields.get("currency")
        curr_val = (curr_field.normalized_value or curr_field.field_value or "USD").upper() if curr_field else "USD"
        evaluations.append(DataQualityResult(
            rule_name="VALID_CURRENCY_CODE",
            rule_category="validity",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="pass" if curr_val in STANDARD_CURRENCIES else "warning",
            severity="medium",
            metric_value=curr_val,
            threshold="ISO-4217 standard currency code",
            details=f"Currency '{curr_val}' validated." if curr_val in STANDARD_CURRENCIES else f"Uncommon currency '{curr_val}'.",
            evaluated_at=eval_time
        ))

        # 3. Non-Negative Monetary Amounts
        tot_field = fields.get("total_amount")
        total_val = None
        if tot_field and tot_field.normalized_value:
            try:
                total_val = float(tot_field.normalized_value)
            except ValueError:
                pass

        evaluations.append(DataQualityResult(
            rule_name="NON_NEGATIVE_AMOUNTS",
            rule_category="accuracy",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="pass" if (total_val is not None and total_val >= 0) else "fail",
            severity="critical",
            metric_value=str(total_val) if total_val is not None else "invalid_or_missing",
            threshold=">= 0.00",
            details="Invoice total is non-negative." if (total_val is not None and total_val >= 0) else "Invalid or negative total amount.",
            evaluated_at=eval_time
        ))

        # 4. Arithmetic Consistency (Subtotal + Tax == Total)
        sub_field = fields.get("subtotal")
        tax_field = fields.get("tax_amount")
        if total_val is not None and sub_field and tax_field:
            try:
                sub_val = float(sub_field.normalized_value or sub_field.field_value)
                tax_val = float(tax_field.normalized_value or tax_field.field_value)
                diff = abs((sub_val + tax_val) - total_val)
                is_consistent = diff <= 0.05
                evaluations.append(DataQualityResult(
                    rule_name="SUBTOTAL_TAX_TOTAL_CONSISTENCY",
                    rule_category="consistency",
                    evaluated_entity_type="document",
                    evaluated_entity_id=doc.id,
                    status="pass" if is_consistent else "fail",
                    severity="high",
                    metric_value=f"diff={round(diff, 2)}",
                    threshold="diff <= 0.05",
                    details=f"Subtotal ({sub_val}) + Tax ({tax_val}) = {sub_val + tax_val} vs Total ({total_val}).",
                    evaluated_at=eval_time
                ))
            except ValueError:
                pass

        # 5. Logical Date Sequence (Due Date >= Invoice Date)
        inv_date_field = fields.get("invoice_date")
        due_date_field = fields.get("due_date")
        if inv_date_field and due_date_field:
            try:
                d_inv = datetime.strptime(inv_date_field.normalized_value, "%Y-%m-%d")
                d_due = datetime.strptime(due_date_field.normalized_value, "%Y-%m-%d")
                is_date_valid = d_due >= d_inv
                evaluations.append(DataQualityResult(
                    rule_name="LOGICAL_DATE_SEQUENCE",
                    rule_category="consistency",
                    evaluated_entity_type="document",
                    evaluated_entity_id=doc.id,
                    status="pass" if is_date_valid else "warning",
                    severity="medium",
                    metric_value=f"Invoice={inv_date_field.normalized_value}, Due={due_date_field.normalized_value}",
                    threshold="Due Date >= Invoice Date",
                    details="Due date is equal to or after invoice date." if is_date_valid else "Due date precedes invoice date.",
                    evaluated_at=eval_time
                ))
            except Exception:
                pass

        # 6. Extraction Confidence Threshold
        conf = doc.extraction_confidence or 0.0
        evaluations.append(DataQualityResult(
            rule_name="EXTRACTION_CONFIDENCE_THRESHOLD",
            rule_category="accuracy",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="pass" if conf >= 0.70 else "warning",
            severity="medium",
            metric_value=f"{round(conf * 100, 1)}%",
            threshold=">= 70.0%",
            details=f"Overall extraction confidence is {round(conf * 100, 1)}%.",
            evaluated_at=eval_time
        ))

        # 7. Duplicate File Detection
        evaluations.append(DataQualityResult(
            rule_name="FILE_HASH_UNIQUENESS",
            rule_category="uniqueness",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="fail" if doc.is_duplicate else "pass",
            severity="high",
            metric_value="duplicate" if doc.is_duplicate else "unique",
            threshold="unique_file_hash",
            details="File hash is unique across system." if not doc.is_duplicate else f"Duplicate of document ID {doc.duplicate_of_id}",
            evaluated_at=eval_time
        ))

        # 8. Search Chunk Coverage
        chunk_count = len(doc.chunks)
        evaluations.append(DataQualityResult(
            rule_name="SEARCH_CHUNK_COVERAGE",
            rule_category="completeness",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="pass" if chunk_count > 0 else "warning",
            severity="low",
            metric_value=str(chunk_count),
            threshold=">= 1 chunk",
            details=f"Generated {chunk_count} text chunks for retrieval.",
            evaluated_at=eval_time
        ))

        # Save to database
        for ev in evaluations:
            db.add(ev)
        db.commit()

        return evaluations

quality_service = DataQualityService()
