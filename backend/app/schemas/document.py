from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class StageEventResponse(BaseModel):
    id: str
    stage: str
    status: str
    duration_ms: Optional[int] = None
    details: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ExtractedFieldResponse(BaseModel):
    id: str
    field_name: str
    field_value: str
    normalized_value: Optional[str] = None
    page_number: int
    supporting_text: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    confidence: Optional[float] = None
    extraction_method: str
    validation_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class InvoiceLineItemResponse(BaseModel):
    id: str
    line_number: int
    description: str
    quantity: float
    unit_price: float
    amount: float
    page_number: int
    confidence: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class DocumentChunkResponse(BaseModel):
    id: str
    chunk_index: int
    page_number: int
    start_char: int
    end_char: int
    content: str
    indexed_in_es: bool
    model_config = ConfigDict(from_attributes=True)

class DocumentListItem(BaseModel):
    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    file_hash: str
    status: str
    document_type: str
    page_count: int
    chunk_count: int
    is_duplicate: bool
    extraction_confidence: Optional[float] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class DocumentDetail(DocumentListItem):
    storage_path: str
    character_count: int
    version: int
    stage_events: List[StageEventResponse] = []
    extracted_fields: List[ExtractedFieldResponse] = []
    line_items: List[InvoiceLineItemResponse] = []
    chunks: List[DocumentChunkResponse] = []
    model_config = ConfigDict(from_attributes=True)
