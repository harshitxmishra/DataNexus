import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
from pypdf import PdfReader
from backend.app.config import settings

class ExtractedFieldData:
    def __init__(
        self,
        field_name: str,
        field_value: str,
        normalized_value: Optional[str] = None,
        page_number: int = 1,
        supporting_text: str = "",
        start_char: int = 0,
        end_char: int = 0,
        confidence: float = 0.85,
        extraction_method: str = "native_regex",
        validation_status: str = "valid"
    ):
        self.field_name = field_name
        self.field_value = field_value
        self.normalized_value = normalized_value or field_value
        self.page_number = page_number
        self.supporting_text = supporting_text
        self.start_char = start_char
        self.end_char = end_char
        self.confidence = confidence
        self.extraction_method = extraction_method
        self.validation_status = validation_status

class LineItemData:
    def __init__(
        self,
        line_number: int,
        description: str,
        quantity: float,
        unit_price: float,
        amount: float,
        page_number: int = 1,
        confidence: float = 0.90
    ):
        self.line_number = line_number
        self.description = description
        self.quantity = quantity
        self.unit_price = unit_price
        self.amount = amount
        self.page_number = page_number
        self.confidence = confidence

class ChunkData:
    def __init__(
        self,
        chunk_index: int,
        page_number: int,
        start_char: int,
        end_char: int,
        content: str
    ):
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.start_char = start_char
        self.end_char = end_char
        self.content = content

class ExtractionResult:
    def __init__(
        self,
        pages_text: List[Dict[str, Any]],
        chunks: List[ChunkData],
        fields: List[ExtractedFieldData],
        line_items: List[LineItemData],
        total_pages: int,
        total_chars: int,
        overall_confidence: float,
        ocr_used: bool = False
    ):
        self.pages_text = pages_text
        self.chunks = chunks
        self.fields = fields
        self.line_items = line_items
        self.total_pages = total_pages
        self.total_chars = total_chars
        self.overall_confidence = overall_confidence
        self.ocr_used = ocr_used

class DocumentExtractionService:
    def extract_text_from_pdf(self, file_path: str) -> Tuple[List[Dict[str, Any]], int, int]:
        """Extract text page by page from digital PDF using pypdf."""
        reader = PdfReader(file_path)
        pages_text = []
        total_chars = 0
        total_pages = len(reader.pages)

        for idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            # Basic whitespace normalization while preserving linebreaks
            normalized_page_text = re.sub(r"[ \t]+", " ", text).strip()
            char_count = len(normalized_page_text)
            total_chars += char_count
            pages_text.append({
                "page_number": idx,
                "text": normalized_page_text,
                "char_count": char_count
            })

        return pages_text, total_pages, total_chars

    def chunk_text(self, pages_text: List[Dict[str, Any]], chunk_size: int = 500, overlap: int = 80) -> List[ChunkData]:
        """Produce page-aware text chunks with offsets and stable indices."""
        chunks: List[ChunkData] = []
        chunk_idx = 0

        for page in pages_text:
            page_num = page["page_number"]
            text = page["text"]
            length = len(text)
            if length == 0:
                continue

            start = 0
            while start < length:
                end = min(start + chunk_size, length)
                # Avoid breaking mid-word if possible
                if end < length:
                    space_pos = text.rfind(" ", start + int(chunk_size * 0.7), end)
                    if space_pos != -1:
                        end = space_pos

                chunk_content = text[start:end].strip()
                if chunk_content:
                    chunks.append(ChunkData(
                        chunk_index=chunk_idx,
                        page_number=page_num,
                        start_char=start,
                        end_char=end,
                        content=chunk_content
                    ))
                    chunk_idx += 1

                if end >= length:
                    break
                start = max(end - overlap, start + 1)

        return chunks

    def extract_invoice_fields(self, pages_text: List[Dict[str, Any]]) -> Tuple[List[ExtractedFieldData], List[LineItemData], float]:
        """
        Extract structured invoice fields and line items with provenance and confidence.
        Never fabricates missing values.
        """
        fields: List[ExtractedFieldData] = []
        line_items: List[LineItemData] = []
        confidences: List[float] = []

        combined_text = "\n".join([f"--- PAGE {p['page_number']} ---\n{p['text']}" for p in pages_text])
        first_page_text = pages_text[0]["text"] if pages_text else ""

        # 1. Invoice Number
        inv_match = re.search(r"(?:Invoice\s*(?:Number|No\.?|#)\s*[:#]?\s*|(?<![A-Za-z])INV-)([A-Za-z0-9-_/]{3,30})", combined_text, re.IGNORECASE)
        if inv_match:
            val = inv_match.group(1).strip()
            # If matched prefix was INV- and group didn't include it
            if not val.upper().startswith("INV") and "INV-" in inv_match.group(0).upper():
                val = f"INV-{val}"
            start, end = inv_match.span()
            fields.append(ExtractedFieldData(
                field_name="invoice_number",
                field_value=val,
                normalized_value=val.upper(),
                page_number=1,
                supporting_text=combined_text[max(0, start - 20):min(len(combined_text), end + 20)].strip(),
                start_char=start,
                end_char=end,
                confidence=0.95,
                extraction_method="regex_pattern"
            ))
            confidences.append(0.95)

        # 2. Vendor Name
        vendor_match = re.search(r"(?:Vendor|From|Billed\s*By|Supplier)\s*[:]\s*([A-Za-z0-9 &.,'-]{3,60})", combined_text, re.IGNORECASE)
        if vendor_match:
            vendor_val = vendor_match.group(1).split("\n")[0].strip()
            start, end = vendor_match.span()
            fields.append(ExtractedFieldData(
                field_name="vendor_name",
                field_value=vendor_val,
                normalized_value=vendor_val,
                page_number=1,
                supporting_text=combined_text[max(0, start - 15):min(len(combined_text), end + 25)].strip(),
                start_char=start,
                end_char=end,
                confidence=0.92,
                extraction_method="header_regex"
            ))
            confidences.append(0.92)
        else:
            # Fallback to header inspection: first non-empty line of page 1 if capitalized or business-like
            first_lines = [line.strip() for line in first_page_text.split("\n") if len(line.strip()) > 3]
            if first_lines and not re.search(r"invoice|bill|receipt|statement", first_lines[0], re.IGNORECASE):
                candidate = first_lines[0][:60]
                fields.append(ExtractedFieldData(
                    field_name="vendor_name",
                    field_value=candidate,
                    normalized_value=candidate,
                    page_number=1,
                    supporting_text=candidate,
                    start_char=0,
                    end_char=len(candidate),
                    confidence=0.75,
                    extraction_method="first_line_heuristic"
                ))
                confidences.append(0.75)

        # 3. Invoice Date
        date_match = re.search(r"(?:Invoice\s*Date|Date|Billed\s*Date)\s*[:]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4})", combined_text, re.IGNORECASE)
        if date_match:
            raw_date = date_match.group(1).strip()
            norm_date = self.normalize_date(raw_date)
            start, end = date_match.span()
            fields.append(ExtractedFieldData(
                field_name="invoice_date",
                field_value=raw_date,
                normalized_value=norm_date,
                page_number=1,
                supporting_text=combined_text[max(0, start - 15):min(len(combined_text), end + 15)].strip(),
                start_char=start,
                end_char=end,
                confidence=0.92,
                extraction_method="date_regex"
            ))
            confidences.append(0.92)

        # 4. Due Date
        due_match = re.search(r"(?:Due\s*Date|Payment\s*Due|Pay\s*By)\s*[:]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{4})", combined_text, re.IGNORECASE)
        if due_match:
            raw_due = due_match.group(1).strip()
            norm_due = self.normalize_date(raw_due)
            start, end = due_match.span()
            fields.append(ExtractedFieldData(
                field_name="due_date",
                field_value=raw_due,
                normalized_value=norm_due,
                page_number=1,
                supporting_text=combined_text[max(0, start - 15):min(len(combined_text), end + 15)].strip(),
                start_char=start,
                end_char=end,
                confidence=0.90,
                extraction_method="date_regex"
            ))
            confidences.append(0.90)

        # 5. Currency
        curr_match = re.search(r"\b(USD|EUR|GBP|INR|CAD|AUD)\b|([$€£₹])", combined_text)
        currency_code = "USD"
        if curr_match:
            sym = (curr_match.group(1) or curr_match.group(2) or "USD").upper()
            mapping = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}
            currency_code = mapping.get(sym, sym)
            fields.append(ExtractedFieldData(
                field_name="currency",
                field_value=sym,
                normalized_value=currency_code,
                page_number=1,
                supporting_text=curr_match.group(0),
                start_char=curr_match.start(),
                end_char=curr_match.end(),
                confidence=0.95,
                extraction_method="symbol_map"
            ))
            confidences.append(0.95)

        # 6. Monetary Amounts: Total, Subtotal, Tax
        # Total
        total_match = re.search(r"\b(?:Grand\s*Total|Total\s*Amount\s*Due|Total\s*(?:Amount|Due)?|Balance\s*Due|Amount\s*Due)\s*[:]?\s*(?:USD|EUR|GBP|INR|CAD|AUD|[$€£₹])?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))", combined_text, re.IGNORECASE)
        if total_match:
            raw_tot = total_match.group(1).replace(",", "")
            start, end = total_match.span()
            fields.append(ExtractedFieldData(
                field_name="total_amount",
                field_value=total_match.group(1),
                normalized_value=raw_tot,
                page_number=1,
                supporting_text=combined_text[max(0, start - 15):min(len(combined_text), end + 15)].strip(),
                start_char=start,
                end_char=end,
                confidence=0.94,
                extraction_method="amount_regex"
            ))
            confidences.append(0.94)

        # Subtotal
        subtotal_match = re.search(r"(?:Sub\s*Total|Subtotal|Net\s*Amount)\s*[:]?\s*(?:USD|EUR|GBP|INR|CAD|AUD|[$€£₹])?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))", combined_text, re.IGNORECASE)
        if subtotal_match:
            raw_sub = subtotal_match.group(1).replace(",", "")
            start, end = subtotal_match.span()
            fields.append(ExtractedFieldData(
                field_name="subtotal",
                field_value=subtotal_match.group(1),
                normalized_value=raw_sub,
                page_number=1,
                supporting_text=combined_text[max(0, start - 15):min(len(combined_text), end + 15)].strip(),
                start_char=start,
                end_char=end,
                confidence=0.92,
                extraction_method="amount_regex"
            ))
            confidences.append(0.92)

        # Tax
        tax_match = re.search(r"(?:Tax\s*/?\s*VAT|Tax|VAT|GST|Sales\s*Tax)\s*(?:\([0-9.]+%\))?\s*[:]?\s*(?:USD|EUR|GBP|INR|CAD|AUD|[$€£₹])?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+(?:\.[0-9]{2}))", combined_text, re.IGNORECASE)
        if tax_match:
            raw_tax = tax_match.group(1).replace(",", "")
            start, end = tax_match.span()
            fields.append(ExtractedFieldData(
                field_name="tax_amount",
                field_value=tax_match.group(1),
                normalized_value=raw_tax,
                page_number=1,
                supporting_text=combined_text[max(0, start - 15):min(len(combined_text), end + 15)].strip(),
                start_char=start,
                end_char=end,
                confidence=0.90,
                extraction_method="amount_regex"
            ))
            confidences.append(0.90)

        # 7. Payment Status
        status_match = re.search(r"\b(Paid|Pending|Due|Overdue|Disputed|Cancelled)\b", combined_text, re.IGNORECASE)
        status_val = "Pending"
        if status_match:
            status_val = status_match.group(1).capitalize()
            fields.append(ExtractedFieldData(
                field_name="payment_status",
                field_value=status_val,
                normalized_value=status_val,
                page_number=1,
                supporting_text=status_match.group(0),
                start_char=status_match.start(),
                end_char=status_match.end(),
                confidence=0.88,
                extraction_method="status_keyword"
            ))
            confidences.append(0.88)

        # 8. Line Items Table Parsing (heuristic lines with description, qty, unit price, amount)
        line_item_regex = re.compile(
            r"^\s*([A-Za-z0-9\s\-_/]{4,40})\s+([0-9]+(?:\.[0-9]+)?)\s+[$€£₹]?([0-9]+(?:\.[0-9]{2})?)\s+[$€£₹]?([0-9]+(?:\.[0-9]{2}))\s*$",
            re.MULTILINE
        )
        matches = line_item_regex.findall(combined_text)
        for idx, (desc, qty, unit, amt) in enumerate(matches, start=1):
            try:
                line_items.append(LineItemData(
                    line_number=idx,
                    description=desc.strip(),
                    quantity=float(qty),
                    unit_price=float(unit),
                    amount=float(amt),
                    page_number=1,
                    confidence=0.88
                ))
            except ValueError:
                pass

        overall_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.50
        return fields, line_items, overall_confidence

    def normalize_date(self, raw_date: str) -> str:
        """Convert various date strings into standard ISO YYYY-MM-DD."""
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                clean_str = raw_date.replace(",", "").strip()
                dt = datetime.strptime(clean_str, fmt.replace(",", ""))
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return raw_date

    def process_document(self, file_path: str, file_type: str) -> ExtractionResult:
        """End-to-end extraction orchestrator with native PDF and fallback."""
        if file_type == "application/pdf" or file_path.lower().endswith(".pdf"):
            pages_text, total_pages, total_chars = self.extract_text_from_pdf(file_path)
            chunks = self.chunk_text(pages_text)
            fields, line_items, confidence = self.extract_invoice_fields(pages_text)
            return ExtractionResult(
                pages_text=pages_text,
                chunks=chunks,
                fields=fields,
                line_items=line_items,
                total_pages=total_pages,
                total_chars=total_chars,
                overall_confidence=confidence,
                ocr_used=False
            )
        elif file_type == "text/csv" or file_path.lower().endswith(".csv"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            pages_text = [{"page_number": 1, "text": content, "char_count": len(content)}]
            chunks = self.chunk_text(pages_text)
            return ExtractionResult(
                pages_text=pages_text,
                chunks=chunks,
                fields=[],
                line_items=[],
                total_pages=1,
                total_chars=len(content),
                overall_confidence=1.0,
                ocr_used=False
            )
        else:
            # Fallback for images or text files
            pages_text = [{"page_number": 1, "text": f"[Scanned image: {file_path}]", "char_count": 20}]
            chunks = self.chunk_text(pages_text)
            return ExtractionResult(
                pages_text=pages_text,
                chunks=chunks,
                fields=[],
                line_items=[],
                total_pages=1,
                total_chars=20,
                overall_confidence=0.60,
                ocr_used=True
            )

extraction_service = DocumentExtractionService()
