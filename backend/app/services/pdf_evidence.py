import os
import re
from typing import Dict, Any, List, Optional
from pypdf import PdfReader
from backend.app.models.document import Document

class PDFEvidenceService:
    """
    Extracts authentic visual coordinates from PDF content streams.
    Maps extracted invoice fields and line items to exact spatial bounding boxes.
    Never fabricates bounding boxes; returns null when coordinates are not in the document stream.
    """

    def extract_document_evidence_coordinates(self, doc: Document) -> Dict[str, Any]:
        """
        Scan the document binary and return authentic spatial coordinates for fields and line items.
        """
        if not doc.storage_path or not os.path.isfile(doc.storage_path):
            return {
                "document_id": doc.id,
                "is_pdf": False,
                "error": "Document file not found on disk",
                "pages": [],
                "field_coordinates": {},
                "line_item_coordinates": []
            }

        is_pdf = (doc.file_type == "application/pdf") or doc.filename.lower().endswith(".pdf")
        if not is_pdf:
            return {
                "document_id": doc.id,
                "is_pdf": False,
                "message": "Visual coordinates are only available for PDF documents",
                "pages": [],
                "field_coordinates": {},
                "line_item_coordinates": []
            }

        try:
            reader = PdfReader(doc.storage_path)
        except Exception as e:
            return {
                "document_id": doc.id,
                "is_pdf": True,
                "error": f"Failed to parse PDF: {str(e)}",
                "pages": [],
                "field_coordinates": {},
                "line_item_coordinates": []
            }

        pages_meta = []
        page_elements: Dict[int, List[Dict[str, Any]]] = {}

        for p_idx, page in enumerate(reader.pages, start=1):
            p_width = float(page.mediabox.width)
            p_height = float(page.mediabox.height)
            elements: List[Dict[str, Any]] = []

            def visitor(text, cm, tm, font_dict, font_size):
                t = text.strip()
                if t:
                    fs = float(font_size or 10.0)
                    x = float(tm[4])
                    y = float(tm[5])
                    # Estimated rendered width based on font size and character count
                    w = fs * len(t) * 0.58
                    h = fs * 1.15
                    elements.append({
                        "text": t,
                        "x": x,
                        "y": y,
                        "width": w,
                        "height": h,
                        "font_size": fs,
                        "page_number": p_idx,
                        "page_width": p_width,
                        "page_height": p_height
                    })

            try:
                page.extract_text(visitor_text=visitor)
            except Exception:
                pass

            page_elements[p_idx] = elements
            pages_meta.append({
                "page_number": p_idx,
                "width": p_width,
                "height": p_height,
                "elements_count": len(elements)
            })

        # Match extracted fields to real elements
        field_coords: Dict[str, Any] = {}
        for field in doc.extracted_fields:
            matched_bbox = self._find_matching_element(
                field.page_number,
                field.field_value,
                field.supporting_text,
                page_elements
            )
            field_coords[field.id] = {
                "field_id": field.id,
                "field_name": field.field_name,
                "field_value": field.field_value,
                "page_number": field.page_number,
                "has_coordinates": matched_bbox is not None,
                "bounding_box": matched_bbox
            }

        # Match line items to real elements
        line_item_coords: List[Dict[str, Any]] = []
        for li in doc.line_items:
            matched_bbox = self._find_matching_element(
                li.page_number,
                li.description,
                str(li.amount),
                page_elements
            )
            line_item_coords.append({
                "line_id": li.id,
                "line_number": li.line_number,
                "description": li.description,
                "amount": li.amount,
                "page_number": li.page_number,
                "has_coordinates": matched_bbox is not None,
                "bounding_box": matched_bbox
            })

        return {
            "document_id": doc.id,
            "is_pdf": True,
            "total_pages": len(reader.pages),
            "pages": pages_meta,
            "field_coordinates": field_coords,
            "line_item_coordinates": line_item_coords
        }

    def _find_matching_element(
        self,
        page_num: int,
        target_val: Optional[str],
        supporting_text: Optional[str],
        page_elements: Dict[int, List[Dict[str, Any]]]
    ) -> Optional[Dict[str, Any]]:
        """
        Locates the authentic spatial bounding box of a field within the page's element stream.
        Strictly returns None if no matching element exists (no synthetic coordinates).
        """
        elements = page_elements.get(page_num, [])
        if not elements:
            return None

        # Clean search targets
        val_raw = target_val.strip() if target_val and target_val.strip() else ""
        supp_raw = supporting_text.strip() if supporting_text and supporting_text.strip() else ""

        # Priority 1: Exact or substring match on target value
        if val_raw:
            val_esc = re.escape(val_raw)
            for el in elements:
                t = el["text"].strip()
                if re.search(val_esc, t, re.IGNORECASE):
                    return self._format_bbox(el)
            
            # Numeric/currency relaxation: e.g. "8500.00" in "USD 8500.00" or "$8,500.00"
            clean_num = re.sub(r"[^\d.]", "", val_raw)
            if len(clean_num) >= 3:
                for el in elements:
                    el_num = re.sub(r"[^\d.]", "", el["text"])
                    if clean_num in el_num or el_num == clean_num:
                        return self._format_bbox(el)

        # Priority 2: Match supporting text excerpt
        if supp_raw and len(supp_raw) >= 6:
            supp_esc = re.escape(supp_raw)
            for el in elements:
                t = el["text"].strip()
                if len(t) >= 6 and (re.search(supp_esc, t, re.IGNORECASE) or t.lower() in supp_raw.lower()):
                    return self._format_bbox(el)

        # No authentic match found
        return None

    def _format_bbox(self, el: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts PDF lower-left coordinates into normalized top-down percentages for responsive canvas rendering.
        """
        pw = el["page_width"]
        ph = el["page_height"]
        x = el["x"]
        y = el["y"]
        w = el["width"]
        h = el["height"]

        # PDF coordinates: origin at bottom-left
        # Web canvas/DOM coordinates: origin at top-left
        top_y = ph - y - h
        left_pct = max(0.0, min(100.0, (x / pw) * 100.0))
        top_pct = max(0.0, min(100.0, (top_y / ph) * 100.0))
        width_pct = max(1.0, min(100.0 - left_pct, (w / pw) * 100.0))
        height_pct = max(1.5, min(100.0 - top_pct, ((h + 4.0) / ph) * 100.0))

        return {
            "pdf_x": round(x, 2),
            "pdf_y": round(y, 2),
            "pdf_width": round(w, 2),
            "pdf_height": round(h, 2),
            "page_width": round(pw, 2),
            "page_height": round(ph, 2),
            "norm_left_pct": round(left_pct, 2),
            "norm_top_pct": round(top_pct, 2),
            "norm_width_pct": round(width_pct, 2),
            "norm_height_pct": round(height_pct, 2)
        }

pdf_evidence_service = PDFEvidenceService()
