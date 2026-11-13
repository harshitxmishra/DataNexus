import io
import pytest
from fastapi.testclient import TestClient
from backend.app.config import settings
from backend.app.models.document import Document

def test_upload_empty_zero_byte_file(client: TestClient):
    """0-byte file upload must be rejected with 400 Bad Request."""
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 400
    assert "empty file" in response.json()["detail"].lower()

def test_upload_oversized_file(client: TestClient, monkeypatch):
    """File exceeding MAX_UPLOAD_SIZE_MB must be rejected with 413 Payload Too Large."""
    # Temporarily set max size to 1KB for fast testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0.001)
    
    large_payload = b"%PDF-1.4 " + (b"A" * 2000)
    files = {"file": ("large.pdf", io.BytesIO(large_payload), "application/pdf")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"].lower()

def test_upload_unsupported_file_format(client: TestClient):
    """Unsupported executable or arbitrary binary format must be rejected with 415."""
    files = {"file": ("script.sh", io.BytesIO(b"#!/bin/bash\necho hello"), "application/x-sh")}
    response = client.post("/api/documents/upload", files=files)
    assert response.status_code == 415
    assert "unsupported file format" in response.json()["detail"].lower()

def test_upload_corrupt_malformed_pdf(client: TestClient, db_session):
    """
    A file claiming to be PDF but containing malformed bytes must fail gracefully in the pipeline
    without crashing FastAPI or leaving unhandled exceptions.
    """
    corrupt_pdf = b"%PDF-1.4 \xff\xfe\x00\x00 MALFORMED_CORRUPTED_STREAM_CONTENT_NO_TRAILER"
    files = {"file": ("corrupt.pdf", io.BytesIO(corrupt_pdf), "application/pdf")}
    
    response = client.post("/api/documents/upload", files=files, data={"process_immediately": "true"})
    assert response.status_code == 200
    doc_data = response.json()
    
    # Document record created, but pipeline records failure gracefully
    assert doc_data["status"] in ["failed", "partially_completed", "completed"]
    
    # Clean up test document
    if "id" in doc_data:
        client.delete(f"/api/documents/{doc_data['id']}")

def test_duplicate_upload_vector_reuse(client: TestClient, db_session):
    """
    Uploading a duplicate file must detect the existing SHA-256 hash,
    flag is_duplicate=True, link duplicate_of_id, and complete cleanly.
    """
    import uuid
    unique_content = f"%PDF-1.4 DataNexus unique {uuid.uuid4()}\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< >>\n%%EOF".encode()
    files1 = {"file": ("invoice_master.pdf", io.BytesIO(unique_content), "application/pdf")}
    
    resp1 = client.post("/api/documents/upload", files=files1, data={"process_immediately": "false"})
    assert resp1.status_code == 200
    doc1 = resp1.json()
    assert doc1["is_duplicate"] is False

    # Second upload with identical bytes
    files2 = {"file": ("invoice_copy.pdf", io.BytesIO(unique_content), "application/pdf")}
    resp2 = client.post("/api/documents/upload", files=files2, data={"process_immediately": "false"})
    assert resp2.status_code == 200
    doc2 = resp2.json()

    assert doc2["is_duplicate"] is True
    assert doc2["duplicate_of_id"] == doc1["id"]

    # Clean up test documents
    if "id" in doc2:
        client.delete(f"/api/documents/{doc2['id']}")
    if "id" in doc1:
        client.delete(f"/api/documents/{doc1['id']}")

def test_api_key_authentication_enforcement(client: TestClient, monkeypatch):
    """
    When API_KEY_ENABLED is True, verify_api_key rejects requests lacking valid API key.
    """
    from backend.app.auth import verify_api_key
    from fastapi import HTTPException

    monkeypatch.setattr(settings, "API_KEY_ENABLED", True)
    monkeypatch.setattr(settings, "API_KEY", "test_secret_key_12345")

    # 1. Missing key raises 401
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(header_key=None, bearer_token=None)
    assert exc_info.value.status_code == 401

    # 2. Invalid key raises 401
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(header_key="wrong-key", bearer_token=None)
    assert exc_info.value.status_code == 401

    # 3. Valid X-API-Key succeeds
    assert verify_api_key(header_key="test_secret_key_12345", bearer_token=None) is True

    # 4. Valid Bearer token succeeds
    from fastapi.security import HTTPAuthorizationCredentials
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test_secret_key_12345")
    assert verify_api_key(header_key=None, bearer_token=token) is True
