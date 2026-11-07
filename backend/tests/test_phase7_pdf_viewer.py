import os
import pytest
from backend.app.models.document import Document, ExtractedField, InvoiceLineItem
from backend.app.services.pdf_evidence import pdf_evidence_service

def test_pdf_evidence_service_real_pdf(db_session):
    """
    Verify authentic spatial bounding box extraction on a real PDF document.
    Coordinates must be extracted from the actual PDF content stream and normalized.
    """
    doc = db_session.query(Document).filter(Document.filename.like("%ApexCloud%")).first()
    assert doc is not None, "Seeded ApexCloud PDF document must exist in database"
    assert os.path.exists(doc.storage_path), f"Source file must exist at {doc.storage_path}"

    result = pdf_evidence_service.extract_document_evidence_coordinates(doc)

    assert result["document_id"] == doc.id
    assert result["is_pdf"] is True
    assert result["total_pages"] >= 1
    assert len(result["pages"]) >= 1

    first_page = result["pages"][0]
    assert first_page["page_number"] == 1
    assert first_page["width"] > 0
    assert first_page["height"] > 0
    assert first_page["elements_count"] > 0

    field_coords = result["field_coordinates"]
    assert len(field_coords) > 0

    # Verify at least one field matched with authentic stream coordinates
    matched_fields = [f for f in field_coords.values() if f["has_coordinates"]]
    assert len(matched_fields) >= 5, "Key invoice fields should match authentic stream elements"

    for f in matched_fields:
        bbox = f["bounding_box"]
        assert bbox is not None
        assert 0.0 <= bbox["norm_left_pct"] <= 100.0
        assert 0.0 <= bbox["norm_top_pct"] <= 100.0
        assert 0.0 < bbox["norm_width_pct"] <= 100.0
        assert 0.0 < bbox["norm_height_pct"] <= 100.0
        assert bbox["pdf_x"] >= 0
        assert bbox["pdf_y"] >= 0

def test_pdf_evidence_service_non_pdf_graceful_handling():
    """
    Verify that non-PDF documents are handled gracefully without exceptions or synthetic boxes.
    """
    dummy_csv = Document(
        id="dummy-csv-doc-id",
        filename="sales_data.csv",
        file_type="text/csv",
        storage_path="data/storage/dummy.csv"
    )

    result = pdf_evidence_service.extract_document_evidence_coordinates(dummy_csv)
    assert result["document_id"] == dummy_csv.id
    assert result["is_pdf"] is False
    assert result["pages"] == []
    assert result["field_coordinates"] == {}
    assert result["line_item_coordinates"] == []

def test_pdf_evidence_service_never_fabricates_coordinates(db_session):
    """
    CRITICAL CONSTRAINT: Never fabricate bounding boxes.
    If a field's value cannot be located in the PDF stream, has_coordinates must be False
    and bounding_box must be None.
    """
    doc = db_session.query(Document).filter(Document.filename.like("%ApexCloud%")).first()
    assert doc is not None

    # Create a synthetic field with non-existent token
    ghost_field = ExtractedField(
        id="ghost-field-test-id",
        document_id=doc.id,
        field_name="ghost_custom_attribute",
        field_value="NON_EXISTENT_TOKEN_XYZ_99999",
        page_number=1,
        supporting_text="Completely nonexistent supporting text",
        confidence=0.5
    )

    # Temporarily append to doc.extracted_fields
    orig_fields = list(doc.extracted_fields)
    doc.extracted_fields.append(ghost_field)

    try:
        result = pdf_evidence_service.extract_document_evidence_coordinates(doc)
        ghost_res = result["field_coordinates"].get("ghost-field-test-id")
        assert ghost_res is not None
        assert ghost_res["has_coordinates"] is False
        assert ghost_res["bounding_box"] is None
    finally:
        doc.extracted_fields = orig_fields

def test_api_get_evidence_coordinates_endpoint(client, db_session):
    """
    Verify GET /api/documents/{document_id}/evidence-coordinates endpoint contract.
    """
    doc = db_session.query(Document).filter(Document.filename.like("%ApexCloud%")).first()
    assert doc is not None

    response = client.get(f"/api/documents/{doc.id}/evidence-coordinates")
    assert response.status_code == 200
    data = response.json()

    assert data["document_id"] == doc.id
    assert data["is_pdf"] is True
    assert "pages" in data
    assert "field_coordinates" in data
    assert "line_item_coordinates" in data

def test_api_evidence_coordinates_404_on_missing_doc(client):
    """
    Verify GET /api/documents/{document_id}/evidence-coordinates returns 404 for unknown document ID.
    """
    response = client.get("/api/documents/non-existent-uuid-0000/evidence-coordinates")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
