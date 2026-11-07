from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from backend.app.models.document import Document, ExtractedField, DocumentChunk
from backend.app.models.data_platform import DataQualityResult
from backend.app.models.analytics import FactInvoice, DimVendor

STANDARD_CURRENCIES = {"USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "CHF", "CNY"}

RULE_SEVERITIES = {
    "REQUIRED_FIELDS_COMPLETENESS": "critical",
    "VALID_CURRENCY_CODE": "medium",
    "NON_NEGATIVE_AMOUNTS": "critical",
    "SUBTOTAL_TAX_TOTAL_CONSISTENCY": "high",
    "LOGICAL_DATE_SEQUENCE": "medium",
    "EXTRACTION_CONFIDENCE_THRESHOLD": "medium",
    "FILE_HASH_UNIQUENESS": "high",
    "SEARCH_CHUNK_COVERAGE": "low",
    "LINE_ITEMS_SUM_CONSISTENCY": "medium",
    "INVOICE_DATE_SANITY": "high",
    "PAYMENT_TERMS_SANITY": "low",
}

class DataQualityService:
    def evaluate_document_quality(self, document_id: str, db: Session, batch_id: Optional[str] = None) -> List[DataQualityResult]:
        """
        Evaluate comprehensive deterministic quality rules for a processed document.
        Idempotent: removes prior evaluations for this document before recording new ones.
        """
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return []

        evaluations: List[DataQualityResult] = []
        eval_time = datetime.now(timezone.utc).replace(tzinfo=None)
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
            severity=RULE_SEVERITIES["REQUIRED_FIELDS_COMPLETENESS"],
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
            severity=RULE_SEVERITIES["VALID_CURRENCY_CODE"],
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
                total_val = float(str(tot_field.normalized_value).replace(",", "").strip())
            except ValueError:
                pass

        evaluations.append(DataQualityResult(
            rule_name="NON_NEGATIVE_AMOUNTS",
            rule_category="accuracy",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="pass" if (total_val is not None and total_val >= 0) else "fail",
            severity=RULE_SEVERITIES["NON_NEGATIVE_AMOUNTS"],
            metric_value=str(total_val) if total_val is not None else "invalid_or_missing",
            threshold=">= 0.00",
            details="Invoice total is non-negative." if (total_val is not None and total_val >= 0) else "Invalid or negative total amount.",
            evaluated_at=eval_time
        ))

        # 4. Arithmetic Consistency (Subtotal + Tax == Total)
        sub_field = fields.get("subtotal")
        tax_field = fields.get("tax_amount")
        sub_val = None
        tax_val = None
        if sub_field and sub_field.normalized_value:
            try:
                sub_val = float(str(sub_field.normalized_value).replace(",", "").strip())
            except ValueError:
                pass
        if tax_field and tax_field.normalized_value:
            try:
                tax_val = float(str(tax_field.normalized_value).replace(",", "").strip())
            except ValueError:
                pass

        if total_val is not None and sub_val is not None and tax_val is not None:
            diff = abs((sub_val + tax_val) - total_val)
            is_consistent = diff <= 0.05
            evaluations.append(DataQualityResult(
                rule_name="SUBTOTAL_TAX_TOTAL_CONSISTENCY",
                rule_category="consistency",
                evaluated_entity_type="document",
                evaluated_entity_id=doc.id,
                status="pass" if is_consistent else "fail",
                severity=RULE_SEVERITIES["SUBTOTAL_TAX_TOTAL_CONSISTENCY"],
                metric_value=f"diff={round(diff, 2)}",
                threshold="diff <= 0.05",
                details=f"Subtotal ({sub_val}) + Tax ({tax_val}) = {round(sub_val + tax_val, 2)} vs Total ({total_val}).",
                evaluated_at=eval_time
            ))
        elif total_val is not None and sub_val is not None:
            diff = abs(sub_val - total_val)
            is_consistent = diff <= 0.05
            evaluations.append(DataQualityResult(
                rule_name="SUBTOTAL_TAX_TOTAL_CONSISTENCY",
                rule_category="consistency",
                evaluated_entity_type="document",
                evaluated_entity_id=doc.id,
                status="pass" if is_consistent else "warning",
                severity=RULE_SEVERITIES["SUBTOTAL_TAX_TOTAL_CONSISTENCY"],
                metric_value=f"diff={round(diff, 2)}",
                threshold="diff <= 0.05",
                details=f"Subtotal ({sub_val}) vs Total ({total_val}) with zero tax.",
                evaluated_at=eval_time
            ))

        # 5. Logical Date Sequence (Due Date >= Invoice Date)
        inv_date_field = fields.get("invoice_date")
        due_date_field = fields.get("due_date")
        d_inv: Optional[date] = None
        d_due: Optional[date] = None

        if inv_date_field and inv_date_field.normalized_value:
            try:
                d_inv = datetime.strptime(inv_date_field.normalized_value, "%Y-%m-%d").date()
            except Exception:
                pass
        if due_date_field and due_date_field.normalized_value:
            try:
                d_due = datetime.strptime(due_date_field.normalized_value, "%Y-%m-%d").date()
            except Exception:
                pass

        if d_inv and d_due:
            is_date_valid = d_due >= d_inv
            evaluations.append(DataQualityResult(
                rule_name="LOGICAL_DATE_SEQUENCE",
                rule_category="consistency",
                evaluated_entity_type="document",
                evaluated_entity_id=doc.id,
                status="pass" if is_date_valid else "warning",
                severity=RULE_SEVERITIES["LOGICAL_DATE_SEQUENCE"],
                metric_value=f"Invoice={d_inv}, Due={d_due}",
                threshold="Due Date >= Invoice Date",
                details="Due date is equal to or after invoice date." if is_date_valid else "Due date precedes invoice date.",
                evaluated_at=eval_time
            ))

        # 6. Extraction Confidence Threshold
        conf = doc.extraction_confidence or 0.0
        evaluations.append(DataQualityResult(
            rule_name="EXTRACTION_CONFIDENCE_THRESHOLD",
            rule_category="accuracy",
            evaluated_entity_type="document",
            evaluated_entity_id=doc.id,
            status="pass" if conf >= 0.70 else "warning",
            severity=RULE_SEVERITIES["EXTRACTION_CONFIDENCE_THRESHOLD"],
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
            severity=RULE_SEVERITIES["FILE_HASH_UNIQUENESS"],
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
            severity=RULE_SEVERITIES["SEARCH_CHUNK_COVERAGE"],
            metric_value=str(chunk_count),
            threshold=">= 1 chunk",
            details=f"Generated {chunk_count} text chunks for retrieval.",
            evaluated_at=eval_time
        ))

        # 9. Line Items Sum Consistency
        if doc.line_items and len(doc.line_items) > 0:
            sum_li = round(sum(li.amount for li in doc.line_items if li.amount is not None), 2)
            target_amount = sub_val if sub_val is not None else total_val
            if target_amount is not None:
                li_diff = abs(sum_li - target_amount)
                li_pass = li_diff <= 0.10
                evaluations.append(DataQualityResult(
                    rule_name="LINE_ITEMS_SUM_CONSISTENCY",
                    rule_category="consistency",
                    evaluated_entity_type="document",
                    evaluated_entity_id=doc.id,
                    status="pass" if li_pass else "warning",
                    severity=RULE_SEVERITIES["LINE_ITEMS_SUM_CONSISTENCY"],
                    metric_value=f"Sum({len(doc.line_items)} items)={sum_li}, Target={target_amount}, diff={round(li_diff, 2)}",
                    threshold="diff <= 0.10",
                    details=f"Line items sum ({sum_li}) matches base amount ({target_amount})." if li_pass else f"Line items sum ({sum_li}) differs from target amount ({target_amount}) by {round(li_diff, 2)}.",
                    evaluated_at=eval_time
                ))
        else:
            evaluations.append(DataQualityResult(
                rule_name="LINE_ITEMS_SUM_CONSISTENCY",
                rule_category="consistency",
                evaluated_entity_type="document",
                evaluated_entity_id=doc.id,
                status="pass",
                severity="low",
                metric_value="0_items",
                threshold="N/A",
                details="No line items extracted for individual item-level audit; skipped.",
                evaluated_at=eval_time
            ))

        # 10. Invoice Date Sanity (Not Future, Post-2000)
        today = datetime.now(timezone.utc).date()
        if d_inv:
            max_future = today + timedelta(days=1)
            min_past = date(2000, 1, 1)
            if d_inv > max_future:
                date_status = "fail"
                date_details = f"Invoice date {d_inv} is set in the future (> {max_future})."
            elif d_inv < min_past:
                date_status = "warning"
                date_details = f"Invoice date {d_inv} is unusually old (< {min_past})."
            else:
                date_status = "pass"
                date_details = f"Invoice date {d_inv} is within valid historical operational window."

            evaluations.append(DataQualityResult(
                rule_name="INVOICE_DATE_SANITY",
                rule_category="validity",
                evaluated_entity_type="document",
                evaluated_entity_id=doc.id,
                status=date_status,
                severity=RULE_SEVERITIES["INVOICE_DATE_SANITY"],
                metric_value=str(d_inv),
                threshold="2000-01-01 <= Date <= Today + 1d",
                details=date_details,
                evaluated_at=eval_time
            ))

        # 11. Payment Terms Sanity (Net terms <= 180 days)
        if d_inv and d_due:
            delta_days = (d_due - d_inv).days
            if 0 <= delta_days <= 180:
                terms_status = "pass"
                terms_details = f"Payment terms span {delta_days} days (standard commercial terms)."
            elif delta_days > 180:
                terms_status = "warning"
                terms_details = f"Unusually extended payment terms span {delta_days} days (> 180 days)."
            else:
                terms_status = "fail"
                terms_details = f"Due date precedes invoice date by {abs(delta_days)} days."

            evaluations.append(DataQualityResult(
                rule_name="PAYMENT_TERMS_SANITY",
                rule_category="validity",
                evaluated_entity_type="document",
                evaluated_entity_id=doc.id,
                status=terms_status,
                severity=RULE_SEVERITIES["PAYMENT_TERMS_SANITY"],
                metric_value=f"{delta_days} days",
                threshold="0 <= Terms <= 180 days",
                details=terms_details,
                evaluated_at=eval_time
            ))

        # Idempotently replace prior evaluations for this document
        db.query(DataQualityResult).filter(
            DataQualityResult.evaluated_entity_type == "document",
            DataQualityResult.evaluated_entity_id == doc.id
        ).delete()

        for ev in evaluations:
            db.add(ev)
        db.commit()

        return evaluations

    def evaluate_all_documents(self, db: Session) -> Dict[str, Any]:
        """Run quality rules evaluation across all documents in the database."""
        docs = db.query(Document).filter(
            Document.status.in_(["completed", "partially_completed"])
        ).all()

        total_rules = 0
        for doc in docs:
            evals = self.evaluate_document_quality(doc.id, db)
            total_rules += len(evals)

        scorecard = self.get_detailed_scorecard(db)
        return {
            "status": "success",
            "documents_evaluated": len(docs),
            "total_rules_evaluated": total_rules,
            "scorecard": scorecard
        }

    def get_detailed_scorecard(self, db: Session) -> Dict[str, Any]:
        """
        Generate detailed quality scorecard aggregating overall metrics,
        breakdown by rule name, and breakdown by quality category.
        """
        total_evals = db.query(func.count(DataQualityResult.id)).scalar() or 0
        passed = db.query(func.count(DataQualityResult.id)).filter(DataQualityResult.status == "pass").scalar() or 0
        failed = db.query(func.count(DataQualityResult.id)).filter(DataQualityResult.status == "fail").scalar() or 0
        warnings = db.query(func.count(DataQualityResult.id)).filter(DataQualityResult.status == "warning").scalar() or 0
        pass_rate = round((passed / total_evals * 100), 1) if total_evals > 0 else 100.0

        # Rule-by-rule breakdown
        rule_rows = db.query(
            DataQualityResult.rule_name,
            DataQualityResult.rule_category,
            DataQualityResult.severity,
            func.count(DataQualityResult.id).label("total"),
            func.sum(case((DataQualityResult.status == "pass", 1), else_=0)).label("passed"),
            func.sum(case((DataQualityResult.status == "fail", 1), else_=0)).label("failed"),
            func.sum(case((DataQualityResult.status == "warning", 1), else_=0)).label("warnings")
        ).group_by(
            DataQualityResult.rule_name,
            DataQualityResult.rule_category,
            DataQualityResult.severity
        ).order_by(DataQualityResult.rule_category, DataQualityResult.rule_name).all()

        by_rule = []
        for r in rule_rows:
            r_total = r[3] or 0
            r_passed = int(r[4] or 0)
            r_failed = int(r[5] or 0)
            r_warnings = int(r[6] or 0)
            r_rate = round((r_passed / r_total * 100), 1) if r_total > 0 else 100.0
            by_rule.append({
                "rule_name": r[0],
                "rule_category": r[1],
                "severity": r[2],
                "total_evaluations": r_total,
                "passed": r_passed,
                "failed": r_failed,
                "warnings": r_warnings,
                "pass_percentage": r_rate
            })

        # Category breakdown
        cat_rows = db.query(
            DataQualityResult.rule_category,
            func.count(DataQualityResult.id).label("total"),
            func.sum(case((DataQualityResult.status == "pass", 1), else_=0)).label("passed"),
            func.sum(case((DataQualityResult.status == "fail", 1), else_=0)).label("failed"),
            func.sum(case((DataQualityResult.status == "warning", 1), else_=0)).label("warnings")
        ).group_by(DataQualityResult.rule_category).order_by(DataQualityResult.rule_category).all()

        by_category = []
        for c in cat_rows:
            c_total = c[1] or 0
            c_passed = int(c[2] or 0)
            c_failed = int(c[3] or 0)
            c_warnings = int(c[4] or 0)
            c_rate = round((c_passed / c_total * 100), 1) if c_total > 0 else 100.0
            by_category.append({
                "rule_category": c[0],
                "total_evaluations": c_total,
                "passed": c_passed,
                "failed": c_failed,
                "warnings": c_warnings,
                "pass_percentage": c_rate
            })

        return {
            "total_evaluations": total_evals,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "pass_rate_percentage": pass_rate,
            "by_rule": by_rule,
            "by_category": by_category
        }

quality_service = DataQualityService()
