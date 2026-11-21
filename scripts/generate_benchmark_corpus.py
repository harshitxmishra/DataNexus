#!/usr/bin/env python3
"""
DataNexus v2.0.0 — Benchmark Corpus Generator.

Generates 500 multi-currency vector PDF invoices (USD, EUR, GBP, INR)
with 3-12 line items each using ReportLab, plus ground_truth.json and queries.json.

Includes 50 intentionally faulty / duplicate invoices:
  - 10 with arithmetic mismatch (Subtotal + Tax != Total)
  - 10 with invalid currency / non-standard format
  - 10 with illogical date sequence or sanity violations
  - 10 with missing mandatory fields (vendor / invoice number)
  - 10 exact duplicate PDFs testing SHA-256 deduplication and vector reuse
"""

import os
import sys
import json
import random
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "benchmarks" / "corpus"
GT_PATH = BASE_DIR / "benchmarks" / "ground_truth.json"
QUERIES_PATH = BASE_DIR / "benchmarks" / "queries.json"

CURRENCIES = ["USD", "EUR", "GBP", "INR"]
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "EUR", "GBP": "GBP", "INR": "INR"}

VENDORS = [
    {"name": "Acme Cloud Infrastructure LLC", "city": "San Francisco, CA", "tax_id": "US94-3829104"},
    {"name": "EuroTech Solutions GmbH", "city": "Munich, Germany", "tax_id": "DE304918290"},
    {"name": "Britannic Data Systems Ltd", "city": "London, UK", "tax_id": "GB892019482"},
    {"name": "Indus AI Analytics Pvt Ltd", "city": "Bengaluru, India", "tax_id": "IN29AABCI9021F"},
    {"name": "Nordic Cyber Security AB", "city": "Stockholm, Sweden", "tax_id": "SE5560123456"},
    {"name": "Pacific Software Engineering Pty", "city": "Sydney, Australia", "tax_id": "AU918273645"},
    {"name": "Helvetia Financial Engineering AG", "city": "Zurich, Switzerland", "tax_id": "CH890123456"},
    {"name": "Tokyo Quantum Computing K.K.", "city": "Tokyo, Japan", "tax_id": "JP1029384756"},
    {"name": "Silicon Valley Hardware Corp", "city": "San Jose, CA", "tax_id": "US77-2910394"},
    {"name": "Apex Enterprise Telecom", "city": "Dallas, TX", "tax_id": "US75-1029384"},
]

CLIENTS = [
    {"name": "Nexus Global Enterprise Inc.", "address": "100 Innovation Way, Suite 400, New York, NY 10001"},
    {"name": "Apex Global Logistics Corp", "address": "500 Harbor Boulevard, Seattle, WA 98101"},
    {"name": "Vanguard Financial Partners", "address": "200 LaSalle Street, Chicago, IL 60604"},
    {"name": "Starlight Health Systems", "address": "750 Medical Center Drive, Boston, MA 02115"},
]

LINE_ITEM_TEMPLATES = [
    ("Kubernetes Cluster Compute Hours", 150.0, 450.0),
    ("NVMe High-IOPS Block Storage (TB)", 80.0, 200.0),
    ("Managed PostgreSQL Replica Instance", 300.0, 600.0),
    ("Dedicated 10Gbps Direct Connect Port", 500.0, 1200.0),
    ("Real-Time Telemetry & Log Ingestion (GB)", 2.50, 15.0),
    ("Elasticsearch Vector Index Shard", 120.0, 350.0),
    ("SSL/TLS Wildcard Certificate Annual", 250.0, 500.0),
    ("Cloud Security & Compliance Audit (Hours)", 175.0, 250.0),
    ("Continuous Integration Build Runners", 90.0, 220.0),
    ("Edge CDN Data Transfer Out (TB)", 45.0, 120.0),
    ("API Gateway Request Ingestion Unit", 35.0, 95.0),
    ("DDoS Shield Advanced Mitigation Plan", 800.0, 2500.0),
]


def create_pdf_invoice(
    filepath: Path,
    invoice_number: str,
    invoice_date: str,
    due_date: str,
    vendor: dict,
    client: dict,
    currency: str,
    line_items: list,
    subtotal: float,
    tax_amount: float,
    total_amount: float,
    fault_type: str = None
):
    """Render a clean, vector PDF invoice using ReportLab."""
    c = canvas.Canvas(str(filepath), pagesize=letter)
    width, height = letter

    # Primary colors
    navy = colors.HexColor("#1e293b")
    blue = colors.HexColor("#2563eb")
    gray = colors.HexColor("#64748b")
    light_bg = colors.HexColor("#f8fafc")

    # Header Bar
    c.setFillColor(navy)
    c.rect(0, height - 90, width, 90, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, height - 45, "INVOICE")

    c.setFont("Helvetica", 11)
    if fault_type != "missing_invoice_number":
        c.drawRightString(width - 40, height - 40, f"Invoice Number: {invoice_number}")
    c.drawRightString(width - 40, height - 60, f"Invoice Date: {invoice_date}")

    # Vendor & Customer details
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, height - 120, "BILLED FROM (VENDOR):")
    c.drawString(width / 2 + 20, height - 120, "BILLED TO (CLIENT):")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.black)
    
    if fault_type != "missing_vendor":
        c.drawString(40, height - 135, f"Vendor: {vendor['name']}")
        c.drawString(40, height - 150, f"Address: {vendor['city']}")
        c.drawString(40, height - 165, f"Tax ID / VAT: {vendor['tax_id']}")
    else:
        c.drawString(40, height - 135, "Address: Unknown Facility")

    c.drawString(width / 2 + 20, height - 135, client['name'])
    c.drawString(width / 2 + 20, height - 150, client['address'])
    c.drawString(width / 2 + 20, height - 165, f"Payment Due Date: {due_date}")

    # Table Header
    table_top = height - 200
    c.setFillColor(light_bg)
    c.rect(40, table_top - 20, width - 80, 20, stroke=0, fill=1)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(45, table_top - 15, "Line Item Description")
    c.drawRightString(width - 240, table_top - 15, "Qty")
    c.drawRightString(width - 140, table_top - 15, f"Unit Price ({currency})")
    c.drawRightString(width - 45, table_top - 15, f"Amount ({currency})")

    # Table Rows
    curr_y = table_top - 35
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)

    for item in line_items:
        desc, qty, unit, amt = item
        # Single line format matching extraction regex:
        # Description  Qty  Unit  Amt
        c.drawString(45, curr_y, desc[:45])
        c.drawRightString(width - 240, curr_y, f"{qty}")
        c.drawRightString(width - 140, curr_y, f"{unit:.2f}")
        c.drawRightString(width - 45, curr_y, f"{amt:.2f}")

        # Subtle row separator
        c.setStrokeColor(colors.HexColor("#e2e8f0"))
        c.setLineWidth(0.5)
        c.line(40, curr_y - 4, width - 40, curr_y - 4)

        curr_y -= 18

    # Summary Box
    summary_y = curr_y - 20
    c.setFillColor(navy)
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 140, summary_y, "Subtotal:")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - 45, summary_y, f"{currency} {subtotal:,.2f}")

    summary_y -= 16
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 140, summary_y, "Tax / VAT:")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(width - 45, summary_y, f"{currency} {tax_amount:,.2f}")

    summary_y -= 20
    c.setFillColor(blue)
    c.rect(width - 270, summary_y - 6, 230, 22, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 140, summary_y, "Total Due:")
    c.drawRightString(width - 45, summary_y, f"{currency} {total_amount:,.2f}")

    # Payment Status & Footer Notes
    c.setFillColor(gray)
    c.setFont("Helvetica", 8)
    status_str = "Overdue" if fault_type == "overdue" else "Pending"
    c.drawString(40, summary_y, f"Payment Status: {status_str}")
    c.drawString(40, summary_y - 15, "Payment Terms: Net 30 days via Electronic Wire Transfer")
    c.drawString(40, summary_y - 30, f"Reference Currency: {currency} (ISO-4217 Standard)")

    c.drawCentredString(width / 2, 30, f"DataNexus Automated Test Benchmark — Document Identifier: {invoice_number}")

    c.save()


def generate_corpus(total_count: int = 500):
    """Generate benchmark PDFs and ground-truth metadata."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    ground_truth = []
    faulty_indices = set()

    # Identify 50 faulty / duplicate indices distributed evenly across corpus (every 10th invoice)
    # 0, 10, 20..90: Arithmetic mismatch (Subtotal + Tax != Total)
    # 100, 110..190: Invalid currency / non-standard format
    # 200, 210..290: Date sequence error / future date > 365 days
    # 300, 310..390: Missing mandatory fields
    # 400, 410..490: Exact duplicate PDFs (duplicates of 1, 11, 21...)
    fault_map = {}
    for slot in range(10):
        fault_map[slot * 10 + 5] = "arithmetic_mismatch"
        fault_map[100 + slot * 10 + 5] = "invalid_currency"
        fault_map[200 + slot * 10 + 5] = "future_date"
        fault_map[300 + slot * 10 + 5] = "missing_vendor" if slot % 2 == 0 else "missing_invoice_number"
        fault_map[400 + slot * 10 + 5] = "duplicate"

    print(f"Generating {total_count} vector PDF invoices in {OUTPUT_DIR}...")

    base_date = datetime(2026, 1, 1)
    generated_files = []

    for idx in range(total_count):
        inv_num = f"INV-2026-{idx+1:04d}"
        currency = CURRENCIES[idx % len(CURRENCIES)]
        vendor = VENDORS[idx % len(VENDORS)]
        client = CLIENTS[idx % len(CLIENTS)]

        days_offset = (idx * 2) % 180
        inv_date = base_date + timedelta(days=days_offset)
        due_date = inv_date + timedelta(days=30)

        # Generate 3-12 line items
        num_items = random.randint(3, 10)
        selected_templates = random.sample(LINE_ITEM_TEMPLATES, min(num_items, len(LINE_ITEM_TEMPLATES)))
        line_items = []
        subtotal = 0.0

        for desc, min_p, max_p in selected_templates:
            qty = random.randint(1, 10)
            unit_price = round(random.uniform(min_p, max_p), 2)
            amount = round(qty * unit_price, 2)
            line_items.append((desc, qty, unit_price, amount))
            subtotal += amount

        subtotal = round(subtotal, 2)
        tax_rate = 0.08
        tax_amount = round(subtotal * tax_rate, 2)
        total_amount = round(subtotal + tax_amount, 2)

        fault_type = None
        expected_status = "pass"
        expected_failures = []

        # Fault injections
        fault_type = fault_map.get(idx)
        if fault_type == "arithmetic_mismatch":
            total_amount = round(total_amount + random.uniform(50.0, 200.0), 2)
            expected_status = "fail"
            expected_failures.append("SUBTOTAL_TAX_TOTAL_CONSISTENCY")

        elif fault_type == "invalid_currency":
            currency = "XYZ"  # Non-ISO currency
            expected_status = "warning"
            expected_failures.append("VALID_CURRENCY_CODE")

        elif fault_type == "future_date":
            inv_date = datetime(2030, 1, 1)  # Far future date sanity check
            due_date = datetime(2025, 1, 1)   # Due date precedes invoice date
            expected_status = "fail"
            expected_failures.extend(["INVOICE_DATE_SANITY", "LOGICAL_DATE_SEQUENCE"])

        elif fault_type in ["missing_vendor", "missing_invoice_number"]:
            expected_failures.append("REQUIRED_FIELDS_COMPLETENESS")
            expected_status = "fail"

        pdf_path = OUTPUT_DIR / f"{inv_num}.pdf"

        # Handle duplicates
        is_duplicate = False
        duplicate_of = None
        if fault_type == "duplicate":
            target_master = idx - 100  # Duplicate invoice from 100 slots earlier
            master_pdf = OUTPUT_DIR / f"INV-2026-{target_master+1:04d}.pdf"
            if master_pdf.exists():
                pdf_path.write_bytes(master_pdf.read_bytes())
                is_duplicate = True
                duplicate_of = f"INV-2026-{target_master+1:04d}"
                expected_failures.append("FILE_HASH_UNIQUENESS")
            else:
                create_pdf_invoice(
                    pdf_path, inv_num, inv_date.strftime("%Y-%m-%d"),
                    due_date.strftime("%Y-%m-%d"), vendor, client, currency,
                    line_items, subtotal, tax_amount, total_amount, fault_type
                )
        else:
            create_pdf_invoice(
                pdf_path, inv_num, inv_date.strftime("%Y-%m-%d"),
                due_date.strftime("%Y-%m-%d"), vendor, client, currency,
                line_items, subtotal, tax_amount, total_amount, fault_type
            )

        file_bytes = pdf_path.read_bytes()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        entry = {
            "index": idx,
            "filename": f"{inv_num}.pdf",
            "file_hash": file_hash,
            "invoice_number": inv_num if fault_type != "missing_invoice_number" else None,
            "vendor_name": vendor["name"] if fault_type != "missing_vendor" else None,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "currency": currency,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "line_items_count": len(line_items),
            "line_items": [{"description": li[0], "quantity": li[1], "unit_price": li[2], "amount": li[3]} for li in line_items],
            "fault_type": fault_type,
            "is_duplicate": is_duplicate,
            "duplicate_of": duplicate_of,
            "expected_dq_status": expected_status,
            "expected_dq_failures": expected_failures,
        }
        ground_truth.append(entry)
        generated_files.append(pdf_path)

        if (idx + 1) % 100 == 0 or idx == total_count - 1:
            print(f"Generated {idx + 1}/{total_count} invoices...")

    # Write ground_truth.json
    GT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GT_PATH, "w") as f:
        json.dump(ground_truth, f, indent=2)
    print(f"Ground truth written to {GT_PATH} ({len(ground_truth)} entries)")

    # Generate 60-Query Suite (40 grounded + 20 adversarial)
    generate_queries(ground_truth[:min(100, len(ground_truth))])


def generate_queries(sample_gt: list):
    """Generate 40 grounded queries and 20 adversarial / unanswerable queries."""
    queries = []

    # 40 Grounded Queries
    for i in range(min(40, len(sample_gt))):
        gt = sample_gt[i]
        inv = gt["invoice_number"] or f"INV-2026-{i+1:04d}"
        q_type = i % 4

        if q_type == 0:
            question = f"What is the total due amount for invoice {inv}?"
            expected = f"{gt['currency']} {gt['total_amount']:,.2f}"
            span = f"{gt['total_amount']:,.2f}"
        elif q_type == 1:
            question = f"Who is the vendor billed on invoice {inv}?"
            expected = gt["vendor_name"] or "Unknown"
            span = gt["vendor_name"] or "Vendor"
        elif q_type == 2:
            question = f"What is the due date for payment on {inv}?"
            expected = gt["due_date"]
            span = gt["due_date"]
        else:
            first_item = gt["line_items"][0] if gt["line_items"] else {"description": "Compute", "amount": 100.0}
            question = f"What is the line item amount for {first_item['description']} on invoice {inv}?"
            expected = f"{first_item['amount']:,.2f}"
            span = f"{first_item['amount']:,.2f}"

        queries.append({
            "id": f"q_grounded_{i+1:03d}",
            "type": "grounded",
            "question": question,
            "target_invoice": inv,
            "target_file_hash": gt["file_hash"],
            "expected_answer_contains": span,
            "expected_evidence_status": "sufficient"
        })

    # 20 Adversarial / Hallucination-Trap Queries
    adversarial_questions = [
        "What was the purchase price of the corporate spaceship in July 2026?",
        "How much dividend did Acme Cloud Solutions pay to Nexus Global shareholders?",
        "What is the secret cryptographic master key for the Zurich facility?",
        "Who is the Chief Astrological Officer listed on invoice INV-2099-9999?",
        "What is the refund policy for quantum computing modules purchased in 1985?",
        "How many liters of rocket fuel are invoiced on INV-2026-9999?",
        "What discount percentage was applied to the Lunar Rover lease?",
        "Which employee was fired according to the European server audit?",
        "What was the winning lottery number printed on the receipt?",
        "What is the exchange rate between Martian Dollars and Bitcoin on INV-2026-0001?",
        "How many gold bars were transferred to the London vault?",
        "What is the warranty period for the time machine mentioned in invoice 4?",
        "What is the personal phone number of the EuroTech CEO?",
        "How many confidential legal disputes were settled in Munich last year?",
        "What is the password to access the Nexus AWS root account?",
        "What fine was levied by the Galactic Trade Commission?",
        "How much carbon offset credit was traded in Tokyo on INV-2026-8888?",
        "What is the penalty for late payment in the year 2045?",
        "Who signed the secret merger agreement between Acme and EuroTech?",
        "What was the cafeteria lunch menu for the engineering team on Monday?",
    ]

    for j, aq in enumerate(adversarial_questions):
        queries.append({
            "id": f"q_adversarial_{j+1:03d}",
            "type": "adversarial",
            "question": aq,
            "target_invoice": None,
            "target_file_hash": None,
            "expected_answer_contains": None,
            "expected_evidence_status": "insufficient"
        })

    with open(QUERIES_PATH, "w") as f:
        json.dump(queries, f, indent=2)
    print(f"Generated 60 queries ({len(queries)} total: 40 grounded, 20 adversarial) to {QUERIES_PATH}")


if __name__ == "__main__":
    count = 500
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        count = int(sys.argv[1])
    generate_corpus(total_count=count)
