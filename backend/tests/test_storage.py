import io
import pytest
from fastapi import UploadFile
from backend.app.services.storage import storage_service, sanitize_filename

def test_sanitize_filename():
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("invoice 2026.pdf") == "invoice_2026.pdf"
    assert sanitize_filename("inv#@123!.pdf") == "inv__123_.pdf"

def test_calculate_file_hash():
    content = b"DataNexus test payload content"
    h1 = storage_service.calculate_file_hash(content)
    h2 = storage_service.calculate_file_hash(content)
    assert len(h1) == 64
    assert h1 == h2

import asyncio

def test_save_upload_pdf():
    pdf_content = b"%PDF-1.4 DataNexus dummy test pdf"
    upload = UploadFile(filename="test_invoice.pdf", file=io.BytesIO(pdf_content))
    file_hash, storage_path, file_size, filename, detected_type = asyncio.run(storage_service.save_upload(upload))
    
    assert file_size == len(pdf_content)
    assert filename == "test_invoice.pdf"
    assert detected_type == "application/pdf"
    assert len(file_hash) == 64
    assert storage_service.read_file(storage_path) == pdf_content
    # Clean up test file
    storage_service.delete_file(storage_path)
