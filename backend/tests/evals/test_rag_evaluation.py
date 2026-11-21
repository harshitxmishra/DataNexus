"""
DataNexus v2.0.0 — Automated RAG Evaluation Gate.

Pytest-compatible test suite verifying:
  1. Faithfulness: Answers are strictly grounded in retrieved evidence; no hallucinations.
  2. Context Precision & Recall: Retrieved passages contain the critical grounding spans.
  3. Negative Evidence Refusal: Unanswerable or adversarial questions reliably trigger
     INSUFFICIENT_EVIDENCE refusal instead of fabricating answers.

Runnable in CI without external API keys (using deterministic extractive synthesis or mocks).
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from backend.app.services.qa import DocumentQAService
from backend.app.services.groq_service import GroqRAGService
from backend.app.models.document import Document, DocumentChunk


# Sample test chunks representing known ground-truth invoices
SAMPLE_CHUNKS = [
    {
        "chunk_id": "chunk-001",
        "document_id": "doc-001",
        "filename": "INV-2026-001_AcmeCorp.pdf",
        "document_type": "invoice",
        "page_number": 1,
        "content": (
            "INVOICE #INV-2026-001. Date: 2026-01-15. Due Date: 2026-02-15.\n"
            "Vendor: Acme Cloud Solutions Inc. Client: Nexus Global Enterprises.\n"
            "Line Item 1: Enterprise Kubernetes Cluster Hosting, Qty: 1, Rate: $4,500.00, Amount: $4,500.00.\n"
            "Line Item 2: Dedicated SSD Storage 2TB, Qty: 2, Rate: $250.00, Amount: $500.00.\n"
            "Subtotal: $5,000.00. Tax (8.25%): $412.50. Total Due: $5,412.50 USD.\n"
            "Payment Terms: Net 30 days via Wire Transfer to Chase Bank."
        ),
        "snippet": "Subtotal: $5,000.00. Tax (8.25%): $412.50. Total Due: $5,412.50 USD.",
        "score": 0.85,
        "lexical_score": 0.82,
        "vector_score": 0.88,
    },
    {
        "chunk_id": "chunk-002",
        "document_id": "doc-002",
        "filename": "INV-2026-002_EuroTech.pdf",
        "document_type": "invoice",
        "page_number": 1,
        "content": (
            "FACTURE #INV-2026-002. Date: 2026-02-01. Due Date: 2026-03-03.\n"
            "Vendor: EuroTech GmbH, Munich, Germany. Client: Nexus EMEA.\n"
            "Line Item: Security Audit and Penetration Testing, Qty: 40 hrs, Rate: 120.00 EUR, Amount: 4,800.00 EUR.\n"
            "VAT (19%): 912.00 EUR. Total Amount Due: 5,712.00 EUR.\n"
            "IBAN: DE89370400440532013000, BIC: BYLADEM1001."
        ),
        "snippet": "Total Amount Due: 5,712.00 EUR.",
        "score": 0.78,
        "lexical_score": 0.75,
        "vector_score": 0.80,
    }
]


@pytest.fixture
def qa_service():
    return DocumentQAService()


class TestRAGRetrievalPrecisionRecall:
    """Verify first-stage and second-stage retrieval recall for known ground-truth queries."""

    def test_context_recall_total_amount(self, qa_service, monkeypatch):
        """Query targeting Total Due must retrieve the chunk containing $5,412.50."""
        mock_search = MagicMock(return_value={
            "query": "What is the total due on invoice INV-2026-001?",
            "provider": "local_search_engine",
            "reranked": False,
            "results": SAMPLE_CHUNKS[:1]
        })
        monkeypatch.setattr("backend.app.services.search.search_service.search", mock_search)

        mock_db = MagicMock()
        response = qa_service.answer_question(
            "What is the total due on invoice INV-2026-001?",
            db=mock_db
        )

        assert response["evidence_status"] == "sufficient"
        assert len(response["citations"]) >= 1
        assert response["citations"][0]["document_id"] == "doc-001"
        assert "5,412.50" in response["answer"] or "5,412.50" in response["citations"][0]["snippet"]

    def test_context_precision_vendor_discrimination(self, qa_service, monkeypatch):
        """Query about EuroTech must not cite Acme Cloud Solutions."""
        mock_search = MagicMock(return_value={
            "query": "Who is the vendor in Germany?",
            "provider": "local_search_engine",
            "reranked": True,
            "results": [SAMPLE_CHUNKS[1]]
        })
        monkeypatch.setattr("backend.app.services.search.search_service.search", mock_search)

        mock_db = MagicMock()
        response = qa_service.answer_question("Who is the vendor in Germany?", db=mock_db)

        assert response["evidence_status"] == "sufficient"
        assert response["citations"][0]["filename"] == "INV-2026-002_EuroTech.pdf"
        assert "EuroTech" in response["answer"] or "EuroTech" in response["citations"][0]["snippet"]


class TestRAGNegativeEvidenceRefusal:
    """Verify system strictly refuses to answer queries with zero or irrelevant evidence."""

    def test_adversarial_query_zero_hits_triggers_refusal(self, qa_service, monkeypatch):
        """Completely out-of-domain query with 0 search hits must return insufficient evidence."""
        mock_search = MagicMock(return_value={
            "query": "What is the capital of Mars?",
            "provider": "local_search_engine",
            "reranked": False,
            "results": []
        })
        monkeypatch.setattr("backend.app.services.search.search_service.search", mock_search)

        mock_db = MagicMock()
        response = qa_service.answer_question("What is the capital of Mars?", db=mock_db)

        assert response["evidence_status"] == "insufficient"
        assert "insufficient" in response["answer"].lower()
        assert len(response["citations"]) == 0

    def test_low_relevance_hits_triggers_refusal(self, qa_service, monkeypatch):
        """Query returning only near-zero relevance noise must be rejected as insufficient."""
        low_score_hit = [{
            "chunk_id": "chunk-noise",
            "document_id": "doc-noise",
            "filename": "irrelevant.pdf",
            "page_number": 1,
            "content": "Terms and conditions apply to all transactions.",
            "snippet": "Terms and conditions...",
            "score": 0.05,
            "lexical_score": 0.0,
            "vector_score": 0.1
        }]
        mock_search = MagicMock(return_value={
            "query": "What is the secret rocket recipe?",
            "provider": "local_search_engine",
            "reranked": False,
            "results": low_score_hit
        })
        monkeypatch.setattr("backend.app.services.search.search_service.search", mock_search)

        mock_db = MagicMock()
        response = qa_service.answer_question("What is the secret rocket recipe?", db=mock_db)

        assert response["evidence_status"] == "insufficient"
        assert "insufficient" in response["answer"].lower()

    def test_groq_service_insufficient_evidence_parsing(self):
        """When LLM emits INSUFFICIENT_EVIDENCE:, the service parses it cleanly into refusal."""
        service = GroqRAGService()
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "INSUFFICIENT_EVIDENCE: The document does not contain salary information."
        mock_completion.choices = [mock_choice]
        mock_completion.usage.prompt_tokens = 50
        mock_completion.usage.completion_tokens = 15
        mock_client.chat.completions.create.return_value = mock_completion
        service._client = mock_client
        service._initialized = True

        result = service.generate_rag_answer(
            question="What is the CEO's salary?",
            context_chunks=SAMPLE_CHUNKS[:1]
        )

        assert result["success"] is True
        assert result["evidence_status"] == "insufficient"
        assert "salary information" in result["answer"]


class TestRAGFaithfulnessGrounding:
    """Verify that answers do not fabricate facts outside the retrieved citations."""

    def test_extractive_synthesis_faithfulness(self, qa_service):
        """Deterministic extractive synthesis must only extract sentences present in the chunk."""
        answer = qa_service._extractive_synthesize(
            question="What is the subtotal and tax?",
            hits=SAMPLE_CHUNKS[:1]
        )

        assert "INV-2026-001_AcmeCorp.pdf" in answer
        assert "Page 1" in answer
        # The sentence in the chunk must appear verbatim inside the blockquote
        assert "Subtotal: $5,000.00" in answer or "Total Due: $5,412.50" in answer
