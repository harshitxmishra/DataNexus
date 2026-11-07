import pytest
from unittest.mock import MagicMock, patch
from backend.app.config import settings
from backend.app.services.groq_service import GroqRAGService, groq_rag_service
from backend.app.services.qa import DocumentQAService

class TestGroqPromptAndGroundingConstruction:
    """Verifies that RAG prompts sent to Groq are strictly formatted and grounded."""

    def test_system_prompt_enforces_grounding_and_insufficient_directive(self):
        service = GroqRAGService()
        assert "DataNexus Document Intelligence Analyst" in service.SYSTEM_PROMPT
        assert "INSUFFICIENT_EVIDENCE:" in service.SYSTEM_PROMPT
        assert "[Source N]" in service.SYSTEM_PROMPT

    @patch("backend.app.services.groq_service.groq_rag_service._get_client")
    def test_context_formatting_includes_source_metadata(self, mock_get_client):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Answer citing [Source 1]."
        mock_resp.usage = MagicMock(prompt_tokens=50, completion_tokens=20)
        mock_client.chat.completions.create.return_value = mock_resp
        mock_get_client.return_value = mock_client

        service = GroqRAGService()
        service._client = mock_client
        service._initialized = True

        chunks = [
            {
                "chunk_id": "chk-123",
                "filename": "Apex_Invoice.pdf",
                "page_number": 2,
                "content": "Total Due: USD 12,450.00"
            }
        ]

        result = service.generate_rag_answer(
            question="What is the total due?",
            context_chunks=chunks,
            model_override="test-model"
        )

        assert result["success"] is True
        assert result["evidence_status"] == "sufficient"
        assert result["model_used"] == "test-model"

        # Verify call arguments
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_msg = call_kwargs["messages"][1]["content"]
        assert "[Source 1: Apex_Invoice.pdf (Page 2, Chunk chk-123)]" in user_msg
        assert "Total Due: USD 12,450.00" in user_msg
        assert "What is the total due?" in user_msg


class TestGroqResponseParsingAndGating:
    """Verifies parsing of sufficient vs insufficient evidence responses."""

    @patch("backend.app.services.groq_service.GroqRAGService._get_client")
    def test_insufficient_evidence_directive_parsing(self, mock_get_client):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            "INSUFFICIENT_EVIDENCE: The documents do not mention laptop warranty periods."
        )
        mock_resp.usage = MagicMock(prompt_tokens=40, completion_tokens=15)
        mock_client.chat.completions.create.return_value = mock_resp
        mock_get_client.return_value = mock_client

        service = GroqRAGService()
        service._client = mock_client
        service._initialized = True

        result = service.generate_rag_answer(
            question="What is the warranty period?",
            context_chunks=[{"filename": "doc.pdf", "page_number": 1, "content": "Some text"}]
        )

        assert result["success"] is True
        assert result["evidence_status"] == "insufficient"
        assert "laptop warranty periods" in result["answer"]
        assert "INSUFFICIENT_EVIDENCE:" not in result["answer"]

    @patch("backend.app.services.groq_service.GroqRAGService._get_client")
    def test_candidate_model_fallback_on_error(self, mock_get_client):
        """Verify that if the primary model fails (e.g. 404), fallback models are attempted."""
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Fallback answer [Source 1]."
        mock_resp.usage = MagicMock(prompt_tokens=30, completion_tokens=10)

        # First call fails, second succeeds
        mock_client.chat.completions.create.side_effect = [
            RuntimeError("Model not found"),
            mock_resp
        ]
        mock_get_client.return_value = mock_client

        service = GroqRAGService()
        service._client = mock_client
        service._initialized = True

        result = service.generate_rag_answer(
            question="Query",
            context_chunks=[{"filename": "doc.pdf", "page_number": 1, "content": "Text"}]
        )

        assert result["success"] is True
        assert result["answer"] == "Fallback answer [Source 1]."
        assert mock_client.chat.completions.create.call_count == 2


class TestGroqResilienceAndQAFallback:
    """Verifies that DocumentQAService gracefully handles Groq unavailability and falls back."""

    @patch("backend.app.services.groq_service.groq_rag_service.is_available", return_value=False)
    def test_unconfigured_groq_falls_back_to_extractive_synthesis(self, mock_available):
        qa = DocumentQAService()
        mock_db = MagicMock()

        # Mock hybrid search returning hits
        with patch("backend.app.services.qa.search_service.search") as mock_search:
            mock_search.return_value = {
                "results": [
                    {
                        "document_id": "doc-1",
                        "filename": "INV-001.pdf",
                        "page_number": 1,
                        "snippet": "Amount Due: USD 500.00",
                        "chunk_id": "chk-1",
                        "content": "Invoice details. Amount Due: USD 500.00 on 2026-05-01.",
                        "lexical_score": 1.5,
                        "score": 0.85
                    }
                ]
            }

            result = qa.answer_question("What is the amount due?", db=mock_db)
            assert result["evidence_status"] == "sufficient"
            assert result["provider_used"] == "extractive_evidence_synthesis"
            assert "INV-001.pdf" in result["answer"]
            assert len(result["citations"]) == 1

    @patch("backend.app.services.groq_service.groq_rag_service.is_available", return_value=True)
    @patch("backend.app.services.groq_service.groq_rag_service.generate_rag_answer")
    def test_failed_groq_call_falls_back_gracefully(self, mock_groq_answer, mock_available):
        mock_groq_answer.return_value = {"success": False, "error": "Connection timed out"}
        qa = DocumentQAService()
        mock_db = MagicMock()

        with patch("backend.app.services.qa.search_service.search") as mock_search:
            mock_search.return_value = {
                "results": [
                    {
                        "document_id": "doc-1",
                        "filename": "INV-001.pdf",
                        "page_number": 1,
                        "snippet": "Amount Due: USD 500.00",
                        "chunk_id": "chk-1",
                        "content": "Invoice details. Amount Due: USD 500.00.",
                        "lexical_score": 1.2,
                        "score": 0.75
                    }
                ]
            }

            result = qa.answer_question("What is the amount due?", db=mock_db)
            assert result["evidence_status"] == "sufficient"
            assert result["provider_used"] == "extractive_evidence_synthesis"
            assert "INV-001.pdf" in result["answer"]


class TestLiveGroqIntegration:
    """Live integration tests executing real requests against GroqCloud API."""

    @pytest.mark.skipif(not bool(getattr(settings, "GROQ_API_KEY", "")), reason="GROQ_API_KEY is not configured")
    def test_live_groq_rag_positive_query_with_citations(self):
        """[Real Integration Test] Query GroqCloud with real context, assert grounding & citations."""
        chunks = [
            {
                "chunk_id": "live-chk-001",
                "filename": "INV-2026-APEX.pdf",
                "page_number": 1,
                "content": (
                    "Apex Cloud Technologies Inc. Statement of Work. "
                    "Total Billed: USD 14,800.00. Payment Terms: Net 30 days. "
                    "Project Lead: Sarah Jenkins."
                )
            }
        ]

        result = groq_rag_service.generate_rag_answer(
            question="Who is the project lead and what is the total billed for Apex Cloud?",
            context_chunks=chunks
        )

        assert result["success"] is True
        assert result["evidence_status"] == "sufficient"
        assert "Sarah Jenkins" in result["answer"]
        assert "14,800" in result["answer"]
        assert "[Source 1]" in result["answer"]
        assert result["latency_ms"] < 6000  # Groq ultra-fast response

    @pytest.mark.skipif(not bool(getattr(settings, "GROQ_API_KEY", "")), reason="GROQ_API_KEY is not configured")
    def test_live_groq_rag_negative_unanswerable_query(self):
        """[Real Integration Test] Query GroqCloud on an unrelated topic, assert insufficient evidence flag."""
        chunks = [
            {
                "chunk_id": "live-chk-002",
                "filename": "INV-2026-APEX.pdf",
                "page_number": 1,
                "content": "Apex Cloud Technologies Inc. Total Billed: USD 14,800.00."
            }
        ]

        result = groq_rag_service.generate_rag_answer(
            question="What is the speed of light in vacuum in miles per hour?",
            context_chunks=chunks
        )

        assert result["success"] is True
        assert result["evidence_status"] == "insufficient"
        assert result["latency_ms"] < 6000

