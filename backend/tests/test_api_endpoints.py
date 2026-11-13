import io

def test_health_endpoints(client):
    r_live = client.get("/api/health/liveness")
    assert r_live.status_code == 200
    assert r_live.json()["status"] == "alive"

    r_ready = client.get("/api/health/readiness")
    assert r_ready.status_code == 200
    data = r_ready.json()
    assert "database" in data
    assert "embedding_provider" in data
    assert data["embedding_provider"]["dimension"] == 384

def test_documents_lifecycle(client):
    # 1. List documents
    r_list = client.get("/api/documents")
    assert r_list.status_code == 200
    docs = r_list.json()
    assert len(docs) >= 1
    # Pick a completed document to test lifecycle, download, and reprocessing
    completed_doc = next((d for d in docs if d.get("status") == "completed"), docs[0])
    doc_id = completed_doc["id"]

    # 2. Document details
    r_detail = client.get(f"/api/documents/{doc_id}")
    assert r_detail.status_code == 200
    detail = r_detail.json()
    assert detail["id"] == doc_id
    assert "stage_events" in detail
    assert "extracted_fields" in detail
    assert "chunks" in detail

    # 3. Download document
    r_down = client.get(f"/api/documents/{doc_id}/download")
    assert r_down.status_code == 200
    assert len(r_down.content) > 0

    # 4. Reprocess document
    r_reproc = client.post(f"/api/documents/{doc_id}/reprocess")
    assert r_reproc.status_code == 200
    assert r_reproc.json()["version"] >= 2

def test_search_and_qa_api(client):
    # Search
    payload = {"query": "logistics air express", "mode": "hybrid", "top_k": 3}
    r_search = client.post("/api/search/query", json=payload)
    assert r_search.status_code == 200
    res = r_search.json()
    assert res["retrieval_mode"] == "hybrid"
    assert len(res["results"]) > 0

    # QA
    qa_payload = {"question": "What services does Global Logistics Partner provide?", "top_k": 3}
    r_qa = client.post("/api/search/qa", json=qa_payload)
    assert r_qa.status_code == 200
    qa_res = r_qa.json()
    assert qa_res["evidence_status"] == "sufficient"
    assert len(qa_res["citations"]) > 0

def test_data_platform_and_analytics_api(client):
    # Pipeline Run
    r_run = client.post("/api/data-platform/pipeline/run")
    assert r_run.status_code == 200
    assert r_run.json()["status"] in ["success", "partially_completed"]

    # Quality Scorecard
    r_score = client.get("/api/data-platform/quality/scorecard")
    assert r_score.status_code == 200
    assert r_score.json()["total_evaluations"] > 0

    # Analytics Overview
    r_over = client.get("/api/analytics/overview")
    assert r_over.status_code == 200
    overview = r_over.json()
    assert overview["total_documents"] >= 5
    assert overview["total_spend_usd"] > 0

    # Vendor spend
    r_spend = client.get("/api/analytics/vendor-spend")
    assert r_spend.status_code == 200
    assert len(r_spend.json()) > 0

    # Overdue invoices
    r_overdue = client.get("/api/analytics/overdue-invoices")
    assert r_overdue.status_code == 200

    # Lineage
    r_list = client.get("/api/documents")
    completed_doc = next((d for d in r_list.json() if d.get("status") == "completed"), r_list.json()[0])
    first_id = completed_doc["id"]
    r_lineage = client.get(f"/api/lineage/document/{first_id}")
    assert r_lineage.status_code == 200
    lin = r_lineage.json()
    assert lin["nodes_count"] > 0
    assert lin["edges_count"] > 0

def test_processing_performance_regression(client):
    """
    Regression test: ensures /api/analytics/processing-performance does not throw HTTP 500
    due to SQLAlchemy func.case vs case() syntax error, and returns valid performance metrics.
    """
    r = client.get("/api/analytics/processing-performance")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if len(data) > 0:
        item = data[0]
        assert "file_type" in item
        assert "total_processed" in item
        assert "success_count" in item
        assert "failure_count" in item
        assert "avg_duration_ms" in item
        assert "ocr_count" in item
        assert "indexed_count" in item
        assert item["total_processed"] >= item["success_count"]
        assert item["avg_duration_ms"] >= 0.0

def test_duplicate_candidates_api(client):
    r = client.get("/api/analytics/duplicate-candidates")
    assert r.status_code == 200
    data = r.json()
    assert "total_duplicates_detected" in data
    assert "candidates" in data

def test_search_status_and_reembed_api(client):
    r_status = client.get("/api/search/status")
    assert r_status.status_code == 200
    status_data = r_status.json()
    assert "active_provider" in status_data
    assert "chunks_current_representation" in status_data
    assert "representation_version" in status_data
    assert status_data["embedding_dimension"] == 384

    r_reembed = client.post("/api/search/reembed?batch_size=10&force_all=false")
    assert r_reembed.status_code == 200
    reembed_data = r_reembed.json()
    assert "reembed" in reembed_data
    assert "status" in reembed_data["reembed"]
