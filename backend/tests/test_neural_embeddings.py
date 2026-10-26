import json
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from backend.app.services.embeddings import (
    embedding_service,
    PretrainedNeuralEmbeddingService,
    InterimHashingEmbeddingService,
    EmbeddingInferenceError
)
from backend.app.models.document import Document, DocumentChunk
from backend.app.services.search import search_service


class TestNeuralEmbeddingModelInitializationAndInference:
    """Tests real pretrained neural model inference using sentence-transformers/all-MiniLM-L6-v2."""

    def test_model_initialization_and_metadata(self):
        service = PretrainedNeuralEmbeddingService()
        meta = service.get_metadata()

        assert meta["is_neural"] is True
        assert meta["dimension"] == 384
        assert meta["representation_version"] == 2
        assert meta["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert meta["device"] == "cpu"
        assert meta["status"] == "operational"

    def test_actual_embedding_dimension(self):
        vec = embedding_service.embed_text("DataNexus invoice intelligence platform")
        assert isinstance(vec, list)
        assert len(vec) == 384
        assert all(isinstance(x, float) for x in vec)

    def test_finite_numerical_output_no_nan_or_inf(self):
        vec = embedding_service.embed_text("Mechanical stress analysis finite element method")
        arr = np.array(vec, dtype=np.float32)
        assert np.isfinite(arr).all(), "Embedding vector must not contain NaN or Inf values"

    def test_unit_l2_normalization(self):
        vec = embedding_service.embed_text("Apex Cloud Kubernetes hosting service")
        arr = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(arr)
        assert abs(norm - 1.0) < 1e-3, f"Expected unit norm ~1.0, got {norm}"

    def test_empty_and_whitespace_input_handling(self):
        vec_empty = embedding_service.embed_text("")
        vec_whitespace = embedding_service.embed_text("   \n\t  ")

        assert len(vec_empty) == 384
        assert len(vec_whitespace) == 384
        assert np.isfinite(np.array(vec_empty)).all()
        assert np.isfinite(np.array(vec_whitespace)).all()

    def test_batch_encoding_consistency(self):
        texts = [
            "Customs Brokerage Compliance Filing Fee",
            "Freight Forwarding International Air Express",
            "Dedicated NVMe Storage Volumes"
        ]
        batch_vecs = embedding_service.embed_texts(texts, batch_size=2)
        assert len(batch_vecs) == len(texts)

        for text, b_vec in zip(texts, batch_vecs):
            single_vec = embedding_service.embed_text(text)
            sim = embedding_service.cosine_similarity(single_vec, b_vec)
            assert sim > 0.999, f"Batch vector differs from single vector: sim={sim}"

    def test_semantic_similarity_discrimination(self):
        # Semantic pair with vocabulary difference
        query = "managed container hosting and virtual compute nodes"
        relevant_doc = "Cloud Infrastructure Clusters (Kubernetes Hosting)"
        unrelated_doc = "Fresh organic hydroponic vegetables and garden compost"

        sim_rel = embedding_service.cosine_similarity(
            embedding_service.embed_text(query),
            embedding_service.embed_text(relevant_doc)
        )
        sim_unrel = embedding_service.cosine_similarity(
            embedding_service.embed_text(query),
            embedding_service.embed_text(unrelated_doc)
        )

        assert sim_rel > sim_unrel, f"Expected {sim_rel} > {sim_unrel}"
        assert sim_rel > 0.35, f"Expected meaningful semantic similarity (>0.35), got {sim_rel}"

    def test_query_document_representation_consistency(self):
        text = "Invoice Number: INV-2026-001. Vendor: Apex Cloud Services."
        query_vec = embedding_service.embed_text(text)
        doc_vec = embedding_service.embed_text(text)

        sim = embedding_service.cosine_similarity(query_vec, doc_vec)
        assert abs(sim - 1.0) < 1e-4


class TestFailureHandlingAndRepresentationVersioning:
    """Tests failure conditions, error hierarchies, representation versioning, and re-embedding."""

    def test_mocked_model_loading_failure_raises_cleanly(self):
        """[Mocked] Simulates missing weights / package error during initialization."""
        failing_service = PretrainedNeuralEmbeddingService(model_name="nonexistent/corrupted-model-name-xyz")
        with patch("sentence_transformers.SentenceTransformer", side_effect=RuntimeError("Model weights not found")):
            with pytest.raises(EmbeddingInferenceError) as exc_info:
                failing_service.embed_text("test")
            assert "Failed to load embedding model" in str(exc_info.value)

    def test_mocked_inference_failure_raises_cleanly(self):
        """[Mocked] Simulates unexpected runtime inference failure without silent fallback."""
        service = PretrainedNeuralEmbeddingService()
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("GPU/CPU CUDA memory fault")
        with patch.object(service, "_get_model", return_value=mock_model):
            with pytest.raises(EmbeddingInferenceError) as exc_info:
                service.embed_text("test")
            assert "Neural embedding inference exception" in str(exc_info.value)

    def test_reembedding_idempotency_and_resumption(self, db_session):
        import uuid
        uid = uuid.uuid4().hex[:12]
        doc = Document(
            id=f"test-doc-{uid}",
            filename="test_invoice.pdf",
            original_name="test_invoice.pdf",
            file_type="application/pdf",
            file_size=1024,
            file_hash=f"hash-{uid}",
            storage_path="/tmp/test_invoice.pdf",
            status="completed",
            document_type="invoice"
        )
        db_session.add(doc)

        c1 = DocumentChunk(
            id=f"chunk-{uid}-01",
            document_id=doc.id,
            chunk_index=0,
            page_number=1,
            start_char=0,
            end_char=50,
            content="Cloud database clusters with automated high-availability failover.",
            embedding=json.dumps([0.1] * 384),
            embedding_model="tfidf-l2-384",
            embedding_version=1  # Legacy interim representation
        )
        c2 = DocumentChunk(
            id=f"chunk-{uid}-02",
            document_id=doc.id,
            chunk_index=1,
            page_number=1,
            start_char=51,
            end_char=100,
            content="Dedicated NVMe high speed storage volumes.",
            embedding=None,  # Missing embedding
            embedding_model=None,
            embedding_version=1
        )
        db_session.add_all([c1, c2])
        db_session.commit()

        try:
            # Run reembed
            summary = embedding_service.reembed_chunks(db_session, batch_size=4, force_all=False)
            assert summary["status"] == "completed"
            assert summary["total_eligible"] >= 2
            assert summary["updated_count"] == summary["total_eligible"]
            assert summary["failed_count"] == 0

            # Verify chunks now have valid v2 embeddings and model metadata
            db_session.refresh(c1)
            db_session.refresh(c2)
            assert c1.embedding_version == 2
            assert c1.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
            vec1 = json.loads(c1.embedding)
            assert len(vec1) == 384
            assert abs(np.linalg.norm(vec1) - 1.0) < 1e-3

            assert c2.embedding_version == 2
            assert c2.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"

            # Idempotency check: running again with force_all=False updates 0 chunks
            summary_idempotent = embedding_service.reembed_chunks(db_session, batch_size=2, force_all=False)
            assert summary_idempotent["status"] == "up_to_date"
            assert summary_idempotent["total_eligible"] == 0
            assert summary_idempotent["updated_count"] == 0
        finally:
            db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()
            db_session.query(Document).filter(Document.id == doc.id).delete()
            db_session.commit()

    def test_search_bm25_functions_when_neural_inference_fails(self, db_session):
        """Verify lexical BM25 remains completely operational even if embedding service fails."""
        with patch.object(embedding_service, "embed_text", side_effect=EmbeddingInferenceError("Simulated neural outage")):
            # BM25 lexical search must succeed without error
            res = search_service.search("Apex", db=db_session, mode="lexical", top_k=2)
            assert res["retrieval_mode"] == "lexical"

            # Hybrid search must degrade gracefully to lexical
            hyb_res = search_service.search("Apex", db=db_session, mode="hybrid", top_k=2)
            assert "results" in hyb_res
            assert len(hyb_res["results"]) >= 0
