from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search term or sentence")
    mode: str = Field("hybrid", description="Retrieval mode: lexical, semantic, or hybrid")
    top_k: int = Field(10, ge=1, le=50)
    document_type: Optional[str] = None

class SearchHitItem(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    document_type: str
    page_number: int
    content: str
    snippet: str
    score: float
    lexical_score: float
    vector_score: float
    retrieval_mode: str

class SearchResponse(BaseModel):
    query: str
    provider: str
    engine: str
    retrieval_mode: str
    total_hits: int
    results: List[SearchHitItem]

class QARequest(BaseModel):
    question: str = Field(..., min_length=2, description="User question over documents")
    top_k: int = Field(5, ge=1, le=20)
    document_type: Optional[str] = None

class QACitation(BaseModel):
    document_id: str
    filename: str
    page_number: int
    snippet: str
    chunk_id: str

class QAResponse(BaseModel):
    question: str
    answer: str
    evidence_status: str  # sufficient or insufficient
    citations: List[QACitation]
    provider_used: str
    latency_ms: int
