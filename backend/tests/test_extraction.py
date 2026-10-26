from backend.app.services.extraction import extraction_service

def test_chunking_offsets():
    pages = [
        {"page_number": 1, "text": "Word " * 200, "char_count": 1000},
        {"page_number": 2, "text": "Page2 content for chunking.", "char_count": 27}
    ]
    chunks = extraction_service.chunk_text(pages, chunk_size=300, overlap=50)
    assert len(chunks) >= 3
    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2
    assert chunks[0].start_char == 0
    assert chunks[0].end_char > 0

def test_extract_invoice_fields():
    invoice_text = """
    ACME INDUSTRIAL SUPPLIES
    Invoice #: INV-998822
    Vendor: Acme Supplies Ltd
    Invoice Date: 2026-10-15
    Due Date: 2026-11-15
    Payment Status: Paid
    Currency: USD

    Line Items:
    Industrial Drill Machine 2 $450.00 $900.00
    Safety Goggles Pack 5 $20.00 $100.00

    Subtotal: $1000.00
    Tax (10%): $100.00
    Total Amount: $1100.00
    """
    pages = [{"page_number": 1, "text": invoice_text, "char_count": len(invoice_text)}]
    fields, line_items, confidence = extraction_service.extract_invoice_fields(pages)
    
    field_map = {f.field_name: f.normalized_value for f in fields}
    assert field_map.get("invoice_number") == "INV-998822"
    assert field_map.get("vendor_name") == "Acme Supplies Ltd"
    assert field_map.get("invoice_date") == "2026-10-15"
    assert field_map.get("due_date") == "2026-11-15"
    assert field_map.get("currency") == "USD"
    assert field_map.get("total_amount") == "1100.00"
    assert confidence >= 0.85
    assert len(line_items) >= 2
