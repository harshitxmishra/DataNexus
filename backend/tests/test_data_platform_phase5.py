import pytest
from datetime import datetime, date, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.app.models.document import Document, ExtractedField, InvoiceLineItem, DocumentChunk
from backend.app.models.analytics import FactInvoice, DimVendor, DimDate
from backend.app.models.data_platform import DataQualityResult, LineageEdge
from backend.app.services.quality import quality_service
from backend.app.services.lineage import lineage_service
from backend.app.services.pipeline import pipeline_service

class TestDataQualityRulesEngine:
    def test_all_11_rules_evaluated_on_document(self, client: TestClient, db_session: Session):
        """Verify that evaluate_document_quality evaluates all 11 enterprise quality rules."""
        doc = db_session.query(Document).filter(Document.status == "completed").first()
        assert doc is not None

        evals = quality_service.evaluate_document_quality(doc.id, db_session)
        assert len(evals) == 11

        rule_names = {e.rule_name for e in evals}
        expected_rules = {
            "REQUIRED_FIELDS_COMPLETENESS",
            "VALID_CURRENCY_CODE",
            "NON_NEGATIVE_AMOUNTS",
            "SUBTOTAL_TAX_TOTAL_CONSISTENCY",
            "LOGICAL_DATE_SEQUENCE",
            "EXTRACTION_CONFIDENCE_THRESHOLD",
            "FILE_HASH_UNIQUENESS",
            "SEARCH_CHUNK_COVERAGE",
            "LINE_ITEMS_SUM_CONSISTENCY",
            "INVOICE_DATE_SANITY",
            "PAYMENT_TERMS_SANITY",
        }
        assert rule_names == expected_rules

    def test_rule_completeness_fails_on_missing_fields(self, db_session: Session):
        """Completeness rule must fail when mandatory invoice fields are missing."""
        doc = Document(
            filename="incomplete_inv.pdf",
            original_name="incomplete_inv.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="dummy_hash_incomplete_1",
            storage_path="data/storage/dummy_incomplete.pdf",
            status="completed",
            document_type="invoice"
        )
        db_session.add(doc)
        db_session.commit()
        try:
            evals = quality_service.evaluate_document_quality(doc.id, db_session)
            comp_rule = next(e for e in evals if e.rule_name == "REQUIRED_FIELDS_COMPLETENESS")
            assert comp_rule.status == "fail"
            assert comp_rule.severity == "critical"
            assert "Missing fields" in comp_rule.details
        finally:
            db_session.query(DataQualityResult).filter(DataQualityResult.evaluated_entity_id == doc.id).delete()
            db_session.query(ExtractedField).filter(ExtractedField.document_id == doc.id).delete()
            db_session.query(Document).filter(Document.id == doc.id).delete()
            db_session.commit()

    def test_rule_non_negative_amounts_fails_on_negative_total(self, db_session: Session):
        """Non-negative amounts rule must fail when total_amount is negative."""
        doc = Document(
            filename="negative_total.pdf",
            original_name="negative_total.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="dummy_hash_neg_1",
            storage_path="data/storage/dummy_neg.pdf",
            status="completed",
            document_type="invoice"
        )
        db_session.add(doc)
        db_session.flush()

        field = ExtractedField(
            document_id=doc.id,
            field_name="total_amount",
            field_value="-500.00",
            normalized_value="-500.00",
            page_number=1,
            extraction_method="regex"
        )
        db_session.add(field)
        db_session.commit()
        try:
            evals = quality_service.evaluate_document_quality(doc.id, db_session)
            neg_rule = next(e for e in evals if e.rule_name == "NON_NEGATIVE_AMOUNTS")
            assert neg_rule.status == "fail"
            assert neg_rule.severity == "critical"
        finally:
            db_session.query(DataQualityResult).filter(DataQualityResult.evaluated_entity_id == doc.id).delete()
            db_session.query(ExtractedField).filter(ExtractedField.document_id == doc.id).delete()
            db_session.query(Document).filter(Document.id == doc.id).delete()
            db_session.commit()

    def test_rule_currency_validation_standard_vs_uncommon(self, db_session: Session):
        """Valid currency code must pass for standard ISO-4217 currencies and warn on unusual ones."""
        doc = Document(
            filename="currency_test.pdf",
            original_name="currency_test.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="dummy_hash_curr_1",
            storage_path="data/storage/dummy_curr.pdf",
            status="completed",
            document_type="invoice"
        )
        db_session.add(doc)
        db_session.flush()

        f_curr = ExtractedField(
            document_id=doc.id,
            field_name="currency",
            field_value="XYZ_TOKEN",
            normalized_value="XYZ_TOKEN",
            page_number=1,
            extraction_method="regex"
        )
        db_session.add(f_curr)
        db_session.commit()
        try:
            evals = quality_service.evaluate_document_quality(doc.id, db_session)
            curr_rule = next(e for e in evals if e.rule_name == "VALID_CURRENCY_CODE")
            assert curr_rule.status == "warning"
        finally:
            db_session.query(DataQualityResult).filter(DataQualityResult.evaluated_entity_id == doc.id).delete()
            db_session.query(ExtractedField).filter(ExtractedField.document_id == doc.id).delete()
            db_session.query(Document).filter(Document.id == doc.id).delete()
            db_session.commit()

    def test_rule_subtotal_tax_consistency_detects_arithmetic_drift(self, db_session: Session):
        """Subtotal + Tax == Total must fail when arithmetic discrepancy exceeds 0.05."""
        doc = Document(
            filename="arithmetic_mismatch.pdf",
            original_name="arithmetic_mismatch.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="dummy_hash_arith_1",
            storage_path="data/storage/dummy_arith.pdf",
            status="completed",
            document_type="invoice"
        )
        db_session.add(doc)
        db_session.flush()

        db_session.add(ExtractedField(document_id=doc.id, field_name="subtotal", field_value="100.00", normalized_value="100.00", page_number=1, extraction_method="regex"))
        db_session.add(ExtractedField(document_id=doc.id, field_name="tax_amount", field_value="10.00", normalized_value="10.00", page_number=1, extraction_method="regex"))
        db_session.add(ExtractedField(document_id=doc.id, field_name="total_amount", field_value="150.00", normalized_value="150.00", page_number=1, extraction_method="regex"))
        db_session.commit()
        try:
            evals = quality_service.evaluate_document_quality(doc.id, db_session)
            sub_rule = next(e for e in evals if e.rule_name == "SUBTOTAL_TAX_TOTAL_CONSISTENCY")
            assert sub_rule.status == "fail"
        finally:
            db_session.query(DataQualityResult).filter(DataQualityResult.evaluated_entity_id == doc.id).delete()
            db_session.query(ExtractedField).filter(ExtractedField.document_id == doc.id).delete()
            db_session.query(Document).filter(Document.id == doc.id).delete()
            db_session.commit()

    def test_rule_future_invoice_date_fails(self, db_session: Session):
        """Invoice date sanity must fail when invoice date is in the future."""
        doc = Document(
            filename="future_date.pdf",
            original_name="future_date.pdf",
            file_type="pdf",
            file_size=1024,
            file_hash="dummy_hash_future_1",
            storage_path="data/storage/dummy_future.pdf",
            status="completed",
            document_type="invoice"
        )
        db_session.add(doc)
        db_session.flush()

        far_future = (datetime.now(timezone.utc).date() + timedelta(days=365)).strftime("%Y-%m-%d")
        db_session.add(ExtractedField(document_id=doc.id, field_name="invoice_date", field_value=far_future, normalized_value=far_future, page_number=1, extraction_method="regex"))
        db_session.commit()
        try:
            evals = quality_service.evaluate_document_quality(doc.id, db_session)
            date_rule = next(e for e in evals if e.rule_name == "INVOICE_DATE_SANITY")
            assert date_rule.status == "fail"
        finally:
            db_session.query(DataQualityResult).filter(DataQualityResult.evaluated_entity_id == doc.id).delete()
            db_session.query(ExtractedField).filter(ExtractedField.document_id == doc.id).delete()
            db_session.query(Document).filter(Document.id == doc.id).delete()
            db_session.commit()

    def test_detailed_scorecard_aggregates_rules_and_categories(self, client: TestClient, db_session: Session):
        """Verify that get_detailed_scorecard returns overall rate, by_rule list, and by_category list."""
        quality_service.evaluate_all_documents(db_session)
        scorecard = quality_service.get_detailed_scorecard(db_session)

        assert scorecard["total_evaluations"] > 0
        assert 0.0 <= scorecard["pass_rate_percentage"] <= 100.0
        assert len(scorecard["by_rule"]) >= 11
        assert len(scorecard["by_category"]) >= 4

        categories = {c["rule_category"] for c in scorecard["by_category"]}
        assert {"completeness", "validity", "accuracy", "consistency"}.issubset(categories)

    def test_quality_evaluate_api_endpoints(self, client: TestClient, db_session: Session):
        """Test POST /api/data-platform/quality/evaluate and GET /api/data-platform/quality/scorecard."""
        # 1. On-demand evaluate all
        r_eval = client.post("/api/data-platform/quality/evaluate")
        assert r_eval.status_code == 200
        data_eval = r_eval.json()
        assert data_eval["status"] == "success"
        assert data_eval["documents_evaluated"] > 0
        assert len(data_eval["scorecard"]["by_rule"]) >= 11

        # 2. Get scorecard
        r_score = client.get("/api/data-platform/quality/scorecard")
        assert r_score.status_code == 200
        score_data = r_score.json()
        assert "by_rule" in score_data
        assert "by_category" in score_data

        # 3. Single document evaluate
        doc = db_session.query(Document).first()
        r_single = client.post(f"/api/data-platform/quality/evaluate?document_id={doc.id}")
        assert r_single.status_code == 200
        assert r_single.json()["documents_evaluated"] == 1


class TestMultiHopLineageGraph:
    def test_document_lineage_contains_full_6_hop_pipeline(self, client: TestClient, db_session: Session):
        """
        Verify that document lineage traces from Raw File -> Document -> Fields -> Fact Invoice -> SQL View -> BI Metric.
        """
        # Ensure dimensional pipeline has run to establish fact and view edges
        pipeline_service.run_invoice_transformation_pipeline(db_session)

        doc = db_session.query(Document).filter(Document.status == "completed").first()
        assert doc is not None

        r = client.get(f"/api/lineage/document/{doc.id}")
        assert r.status_code == 200
        graph = r.json()

        assert graph["nodes_count"] >= 6
        assert graph["edges_count"] >= 5

        node_types = {n["type"] for n in graph["nodes"]}
        expected_types = {"file", "document", "extracted_field", "fact_invoice", "view", "metric"}
        assert expected_types.issubset(node_types)

        # Check metadata enrichment on nodes
        doc_node = next(n for n in graph["nodes"] if n["type"] == "document")
        assert doc_node["metadata"] is not None
        assert "filename" in doc_node["metadata"]

        fact_node = next(n for n in graph["nodes"] if n["type"] == "fact_invoice")
        assert fact_node["metadata"] is not None
        assert "total_amount" in fact_node["metadata"]

    def test_lineage_directional_filtering(self, client: TestClient, db_session: Session):
        """Verify that upstream returns provenance to file, while downstream returns facts and metrics."""
        pipeline_service.run_invoice_transformation_pipeline(db_session)
        doc = db_session.query(Document).filter(Document.status == "completed").first()

        # Upstream: only file and document
        r_up = client.get(f"/api/lineage/document/{doc.id}?direction=upstream")
        assert r_up.status_code == 200
        up_types = {n["type"] for n in r_up.json()["nodes"]}
        assert "file" in up_types
        assert "view" not in up_types
        assert "metric" not in up_types

        # Downstream: document, fields, facts, views, metrics
        r_down = client.get(f"/api/lineage/document/{doc.id}?direction=downstream")
        assert r_down.status_code == 200
        down_types = {n["type"] for n in r_down.json()["nodes"]}
        assert "file" not in down_types
        assert "fact_invoice" in down_types
        assert "view" in down_types

    def test_node_lineage_rooted_at_fact_invoice(self, client: TestClient, db_session: Session):
        """Verify traversing lineage rooted at a fact_invoice node."""
        pipeline_service.run_invoice_transformation_pipeline(db_session)
        fact = db_session.query(FactInvoice).first()
        assert fact is not None

        r = client.get(f"/api/lineage/node/fact_invoice/{fact.invoice_key}")
        assert r.status_code == 200
        graph = r.json()
        assert graph["nodes_count"] > 0
        node_types = {n["type"] for n in graph["nodes"]}
        assert "fact_invoice" in node_types

    def test_lineage_summary_api(self, client: TestClient):
        """Verify GET /api/lineage/summary returns global graph topology."""
        r = client.get("/api/lineage/summary")
        assert r.status_code == 200
        summary = r.json()
        assert summary["total_nodes"] > 0
        assert summary["total_edges"] > 0
        assert "nodes_by_type" in summary
        assert "edges_by_rule" in summary


class TestCuratedAnalyticalViewsAndPowerBi:
    def test_list_analytical_views_returns_all_7_views(self, client: TestClient):
        """Verify GET /api/analytics/views returns the 7 curated SQL views with domain & row counts."""
        r = client.get("/api/analytics/views")
        assert r.status_code == 200
        data = r.json()
        assert len(data["views"]) == 7

        view_names = {v["view_name"] for v in data["views"]}
        expected_views = {
            "v_daily_ingestion",
            "v_processing_performance",
            "v_invoice_spend_by_vendor",
            "v_overdue_invoices",
            "v_data_quality_scorecard",
            "v_pipeline_freshness",
            "v_indexing_coverage"
        }
        assert view_names == expected_views

    def test_query_curated_view_pagination_and_columns(self, client: TestClient):
        """Verify querying a curated analytical view dynamically with pagination."""
        r = client.get("/api/analytics/views/v_invoice_spend_by_vendor?skip=0&limit=5")
        assert r.status_code == 200
        view_res = r.json()
        assert view_res["view_name"] == "v_invoice_spend_by_vendor"
        assert view_res["returned_rows"] <= 5
        assert "vendor_name" in view_res["columns"]
        assert "total_spend" in view_res["columns"]

    def test_query_curated_view_sql_injection_rejection(self, client: TestClient):
        """Invalid or malicious view names must be rejected with HTTP 400."""
        r = client.get("/api/analytics/views/documents;DROP TABLE documents;--")
        assert r.status_code == 400
        assert "Invalid view name" in r.json()["detail"]

    def test_powerbi_semantic_model_specification(self, client: TestClient):
        """Verify GET /api/analytics/powerbi/semantic-model returns complete schema, relationships, and DAX measures."""
        r = client.get("/api/analytics/powerbi/semantic-model")
        assert r.status_code == 200
        model = r.json()

        assert "dataset_name" in model
        assert len(model["tables"]) == 6
        assert len(model["relationships"]) == 4
        assert len(model["dax_measures"]) >= 8
        assert len(model["curated_views"]) == 7
        assert model["connection_parameters"]["database"] == "datanexus"

        # Check DAX measures structure
        spend_dax = next(m for m in model["dax_measures"] if m["name"] == "Total Invoiced Spend USD")
        assert "CALCULATE(SUM(fact_invoice[total_amount])" in spend_dax["expression"]

        overdue_dax = next(m for m in model["dax_measures"] if m["name"] == "Overdue Liability Exposure")
        assert "CALCULATE(SUM(fact_invoice[total_amount])" in overdue_dax["expression"]

    def test_invoices_csv_export(self, client: TestClient):
        """Verify GET /api/data-platform/export/invoices streams valid CSV with correct headers."""
        r = client.get("/api/data-platform/export/invoices")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        text_content = r.text
        lines = text_content.strip().split("\n")
        assert len(lines) >= 2
        header = lines[0].strip().split(",")
        assert "invoice_number" in header
        assert "vendor_name" in header
        assert "total_amount" in header
