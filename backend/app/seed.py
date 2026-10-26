import os
import hashlib
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from backend.app.config import BASE_DIR, settings
from backend.app.database import SessionLocal, Base, engine
from backend.app.models.views import init_analytical_views
from backend.app.models.document import Document
from backend.app.models.data_platform import StagedCsvRecord
from backend.app.services.queue import queue_service

INVOICE_SAMPLES = [
    {
        "filename": "INV-2026-001-ApexCloud.pdf",
        "vendor": "Apex Cloud Services",
        "invoice_num": "INV-2026-001",
        "date": "2026-09-15",
        "due_date": "2026-10-15",
        "currency": "USD",
        "subtotal": "11500.00",
        "tax": "950.00",
        "total": "12450.00",
        "status": "Paid",
        "lines": [
            ("Cloud Infrastructure Clusters (Kubernetes Hosting)", "1", "8500.00", "8500.00"),
            ("Dedicated NVMe Storage Volumes (50TB Tier)", "1", "2000.00", "2000.00"),
            ("Direct Connect Enterprise Bandwidth", "1", "1000.00", "1000.00"),
        ]
    },
    {
        "filename": "INV-2026-002-GlobalLogistics.pdf",
        "vendor": "Global Logistics Partner",
        "invoice_num": "INV-2026-002",
        "date": "2026-09-28",
        "due_date": "2026-10-28",
        "currency": "USD",
        "subtotal": "8000.00",
        "tax": "720.50",
        "total": "8720.50",
        "status": "Paid",
        "lines": [
            ("Freight Forwarding International Air Express", "2", "3200.00", "6400.00"),
            ("Customs Brokerage Compliance Filing Fee", "1", "1600.00", "1600.00"),
        ]
    },
    {
        "filename": "INV-2026-003-StarlightLabs.pdf",
        "vendor": "Starlight Software Labs",
        "invoice_num": "INV-2026-003",
        "date": "2026-10-05",
        "due_date": "2026-11-05",
        "currency": "EUR",
        "subtotal": "13500.00",
        "tax": "1800.00",
        "total": "15300.00",
        "status": "Pending",
        "lines": [
            ("AI Platform Engineering Consulting (Sprint 14)", "1", "9000.00", "9000.00"),
            ("Architecture Review & Security Penetration Audit", "1", "4500.00", "4500.00"),
        ]
    },
    {
        "filename": "INV-2026-004-MeridianFacilities.pdf",
        "vendor": "Meridian Facilities Corp",
        "invoice_num": "INV-2026-004",
        "date": "2026-08-20",
        "due_date": "2026-09-20",  # Deliberately past due date to trigger overdue fact
        "currency": "USD",
        "subtotal": "4250.00",
        "tax": "400.00",
        "total": "4650.00",
        "status": "Overdue",
        "lines": [
            ("Headquarters HVAC System Overhaul Maintenance", "1", "2750.00", "2750.00"),
            ("Data Center Environmental Filter Replacement", "1", "1500.00", "1500.00"),
        ]
    },
    {
        "filename": "INV-2026-005-NordicData.pdf",
        "vendor": "Nordic Data Systems",
        "invoice_num": "INV-2026-005",
        "date": "2026-10-12",
        "due_date": "2026-11-12",
        "currency": "EUR",
        "subtotal": "8800.00",
        "tax": "1000.00",
        "total": "9800.00",
        "status": "Paid",
        "lines": [
            ("High Performance Analytical Database License", "1", "7200.00", "7200.00"),
            ("Enterprise 24x7 SLA Support Subscription", "1", "1600.00", "1600.00"),
        ]
    },
    {
        "filename": "INV-2026-006-PinnacleEng.pdf",
        "vendor": "Pinnacle Engineering Group",
        "invoice_num": "INV-2026-006",
        "date": "2026-10-18",
        "due_date": "2026-11-18",
        "currency": "GBP",
        "subtotal": "19000.00",
        "tax": "2150.00",
        "total": "21150.00",
        "status": "Pending",
        "lines": [
            ("Core Network Backbone Fiber Optic Splicing", "1", "12500.00", "12500.00"),
            ("Redundant Router Hardware Configuration", "1", "6500.00", "6500.00"),
        ]
    }
]

def generate_pdf_invoice(filepath: str, data: dict):
    """Draw a clean, professional vector PDF invoice using reportlab."""
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter

    # Header Bar
    c.setFillColor(colors.HexColor("#0f172a"))  # Deep slate
    c.rect(0, height - 80, width, 80, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, height - 50, "DATANEXUS COMMERCIAL INVOICE")

    c.setFont("Helvetica", 10)
    c.drawString(40, height - 68, "Document Intelligence & Business Intelligence Demonstration Dataset")

    # Invoice Metadata Section
    c.setFillColor(colors.HexColor("#1e293b"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 120, f"Vendor: {data['vendor']}")

    c.setFont("Helvetica", 10)
    c.drawString(40, height - 140, f"Invoice #: {data['invoice_num']}")
    c.drawString(40, height - 155, f"Invoice Date: {data['date']}")
    c.drawString(40, height - 170, f"Due Date: {data['due_date']}")

    c.drawString(380, height - 140, f"Payment Status: {data['status']}")
    c.drawString(380, height - 155, f"Currency: {data['currency']}")
    c.drawString(380, height - 170, f"Verification: Synthetic Demonstration Seed")

    # Table Header
    c.setFillColor(colors.HexColor("#f1f5f9"))
    c.rect(40, height - 215, width - 80, 25, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, height - 202, "Line Item Description")
    c.drawString(340, height - 202, "Qty")
    c.drawString(400, height - 202, "Unit Price")
    c.drawString(480, height - 202, "Amount")

    # Line Items
    y = height - 235
    c.setFont("Helvetica", 9)
    for desc, qty, unit, amt in data["lines"]:
        c.setFillColor(colors.HexColor("#334155"))
        c.drawString(50, y, desc[:45])
        c.drawString(345, y, qty)
        c.drawString(400, y, f"{data['currency']} {unit}")
        c.drawString(480, y, f"{data['currency']} {amt}")
        y -= 25

    # Totals Divider
    c.setStrokeColor(colors.HexColor("#cbd5e1"))
    c.setLineWidth(1)
    c.line(40, y + 10, width - 40, y + 10)

    # Totals block
    y -= 15
    c.setFont("Helvetica-Bold", 10)
    c.drawString(350, y, "Subtotal:")
    c.drawString(460, y, f"{data['currency']} {data['subtotal']}")

    y -= 20
    c.drawString(350, y, "Tax / VAT:")
    c.drawString(460, y, f"{data['currency']} {data['tax']}")

    y -= 22
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawString(350, y, "Total Amount Due:")
    c.drawString(460, y, f"{data['currency']} {data['total']}")

    # Footer Notes & Traceability Notice
    c.setFillColor(colors.HexColor("#64748b"))
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, 45, "Traceability Notice: This invoice is indexed in the DataNexus dimensional model and semantic retrieval catalog.")
    c.drawString(40, 32, f"Source File ID: {data['filename']} | Lineage Anchor: dim_vendor -> fact_invoice -> v_invoice_spend_by_vendor")

    c.showPage()
    c.save()

def seed_database():
    """Seed sample PDFs and execute processing to populate demonstration data."""
    print("--- Starting DataNexus Database Seed ---")
    Base.metadata.create_all(bind=engine)
    init_analytical_views(engine)

    sample_dir = BASE_DIR / "sample_data" / "sample_invoices"
    csv_dir = BASE_DIR / "sample_data" / "sample_csv"
    sample_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()

    # Generate and process sample invoices
    for sample in INVOICE_SAMPLES:
        pdf_path = sample_dir / sample["filename"]
        generate_pdf_invoice(str(pdf_path), sample)
        
        # Read content to calculate hash
        with open(pdf_path, "rb") as f:
            content = f.read()
        file_hash = hashlib.sha256(content).hexdigest()
        file_size = len(content)

        # Check if already seeded
        existing = db.query(Document).filter(Document.file_hash == file_hash).first()
        if existing:
            print(f"Skipping existing seeded document: {sample['filename']}")
            continue

        # Save to storage path
        stored_path = Path(settings.STORAGE_DIR) / f"{file_hash[:12]}_{sample['filename']}"
        with open(stored_path, "wb") as f:
            f.write(content)

        doc = Document(
            filename=sample["filename"],
            original_name=sample["filename"],
            file_type="application/pdf",
            file_size=file_size,
            file_hash=file_hash,
            storage_path=str(stored_path),
            document_type="invoice",
            status="uploaded"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        print(f"Executing pipeline for {sample['filename']}...")
        queue_service.execute_document_pipeline(doc.id, db)

    # Generate sample CSV master dataset
    csv_path = csv_dir / "vendor_contracts_master.csv"
    csv_content = (
        "contract_id,vendor_name,service_category,annual_cap_usd,payment_terms,sla_target,auto_renew\n"
        "CNT-101,Apex Cloud Services,Cloud Infrastructure,150000.00,Net 30,99.99%,TRUE\n"
        "CNT-102,Global Logistics Partner,Logistics & Freight,100000.00,Net 30,98.50%,TRUE\n"
        "CNT-103,Starlight Software Labs,Engineering Consulting,180000.00,Net 30,99.00%,FALSE\n"
        "CNT-104,Meridian Facilities Corp,Facility Management,60000.00,Net 30,95.00%,TRUE\n"
        "CNT-105,Nordic Data Systems,Database Software,120000.00,Net 30,99.95%,TRUE\n"
        "CNT-106,Pinnacle Engineering Group,Network Infrastructure,250000.00,Net 30,99.90%,TRUE\n"
    )
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(csv_content)

    db.close()
    print("--- DataNexus Seed Completed Successfully ---")

if __name__ == "__main__":
    seed_database()
