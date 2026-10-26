import json
import socket
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from backend.app.services.search import (
    ElasticsearchProvider,
    LocalSearchProvider,
    SearchService,
    SearchResult,
    DATANEXUS_INDEX_MAPPINGS,
    INDEX_SETTINGS
)
from backend.app.models.document import Document, DocumentChunk


class TestElasticsearchMappingsAndQueryConstruction:
    """Verifies that Elasticsearch index mappings and DSL queries match target specifications."""

    def test_index_mappings_has_expected_types_and_dimensions(self):
        props = DATANEXUS_INDEX_MAPPINGS["properties"]

        assert props["chunk_id"]["type"] == "keyword"
        assert props["document_id"]["type"] == "keyword"
        assert props["filename"]["type"] == "keyword"
        assert props["document_type"]["type"] == "keyword"
        assert props["page_number"]["type"] == "integer"
        assert props["chunk_index"]["type"] == "integer"
        assert props["start_char"]["type"] == "integer"
        assert props["end_char"]["type"] == "integer"
        assert props["content"]["type"] == "text"
        assert props["created_at"]["type"] == "date"

        # Dense vector mapping specification
        emb = props["embedding"]
        assert emb["type"] == "dense_vector"
        assert emb["dims"] == 384
        assert emb["similarity"] == "cosine"
        assert emb["index"] is True

    def test_index_settings_single_shard_for_local_resilience(self):
        assert INDEX_SETTINGS["number_of_shards"] == 1
        assert INDEX_SETTINGS["number_of_replicas"] == 0

    @patch("backend.app.services.search.Elasticsearch")
    def test_bm25_lexical_query_structure_and_boosting(self, mock_es_class):
        """[Mocked Unit Test] Verify BM25 multi_match query fields, boosting, and filtering."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 4.82,
                        "_source": {
                            "chunk_id": "c-101",
                            "document_id": "d-202",
                            "filename": "invoice_apex.pdf",
                            "document_type": "invoice",
                            "page_number": 1,
                            "content": "Invoice Total: $12,450.00 Apex Cloud Services",
                        },
                        "highlight": {
                            "content": ["<em>Invoice Total</em>: $12,450.00"]
                        }
                    }
                ]
            }
        }
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        mock_db = MagicMock()

        results, mode_label = provider.search(
            query="Invoice Total Apex",
            db=mock_db,
            mode="lexical",
            top_k=5,
            doc_type_filter="invoice"
        )

        assert mode_label == "elasticsearch_bm25"
        assert len(results) == 1
        assert results[0].chunk_id == "c-101"
        assert results[0].score == 4.82
        assert results[0].retrieval_mode == "lexical"

        # Inspect DSL call arguments
        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["index"] == provider.index_name
        assert call_kwargs["size"] == 5
        query_clause = call_kwargs["query"]["bool"]
        must_match = query_clause["must"][0]["multi_match"]
        assert "content^2.0" in must_match["fields"]
        assert "filename^1.0" in must_match["fields"]
        assert query_clause["filter"] == [{"term": {"document_type": "invoice"}}]

    @patch("backend.app.services.search.Elasticsearch")
    def test_semantic_knn_query_structure(self, mock_es_class):
        """[Mocked Unit Test] Verify kNN vector search parameters and candidate counts."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.895,
                        "_source": {
                            "chunk_id": "c-102",
                            "document_id": "d-202",
                            "filename": "invoice_apex.pdf",
                            "document_type": "invoice",
                            "page_number": 1,
                            "content": "Cloud compute nodes pricing details",
                        }
                    }
                ]
            }
        }
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        mock_db = MagicMock()

        results, mode_label = provider.search(
            query="server infrastructure",
            db=mock_db,
            mode="semantic",
            top_k=10
        )

        assert mode_label == "elasticsearch_knn"
        assert len(results) == 1
        assert results[0].vector_score == 0.895
        assert results[0].retrieval_mode == "semantic"

        call_kwargs = mock_client.search.call_args[1]
        knn_args = call_kwargs["knn"]
        assert knn_args["field"] == "embedding"
        assert knn_args["k"] == 10
        assert knn_args["num_candidates"] == 50
        assert len(knn_args["query_vector"]) == 384

    @patch("backend.app.services.search.Elasticsearch")
    def test_hybrid_rrf_rank_fusion_structure(self, mock_es_class):
        """[Mocked Unit Test] Verify Reciprocal Rank Fusion configuration."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.0325,
                        "_source": {
                            "chunk_id": "c-103",
                            "document_id": "d-203",
                            "filename": "invoice_globex.pdf",
                            "document_type": "invoice",
                            "page_number": 1,
                            "content": "Globex Corporation freight shipping",
                        }
                    }
                ]
            }
        }
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        mock_db = MagicMock()

        results, mode_label = provider.search(
            query="Globex freight",
            db=mock_db,
            mode="hybrid",
            top_k=5
        )

        assert mode_label == "elasticsearch_hybrid_rrf"
        assert len(results) == 1
        call_kwargs = mock_client.search.call_args[1]
        assert "rank" in call_kwargs
        assert call_kwargs["rank"]["rrf"]["window_size"] == 50
        assert call_kwargs["rank"]["rrf"]["rank_constant"] == 60


class TestElasticsearchIndexingAndPropagation:
    """Verifies indexing lifecycle, deterministic IDs, bulk indexing, and deletion propagation."""

    @patch("backend.app.services.search.Elasticsearch")
    def test_idempotent_chunk_upsert_deterministic_id(self, mock_es_class):
        """[Mocked Unit Test] Verify chunk upsert uses chunk.id as Elasticsearch _id."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()

        chunk = DocumentChunk(
            id="test-chunk-abc-123",
            document_id="doc-xyz-789",
            chunk_index=0,
            page_number=2,
            start_char=150,
            end_char=450,
            content="Testing chunk indexing in Elasticsearch",
            created_at=datetime.utcnow()
        )
        doc = Document(
            id="doc-xyz-789",
            filename="test_doc.pdf",
            document_type="invoice",
            version=1
        )
        fake_vector = [0.05] * 384

        success = provider.index_chunk(chunk, doc, fake_vector)
        assert success is True

        mock_client.index.assert_called_once()
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["index"] == provider.index_name
        assert call_kwargs["id"] == "test-chunk-abc-123"
        doc_body = call_kwargs["document"]
        assert doc_body["chunk_id"] == "test-chunk-abc-123"
        assert doc_body["document_id"] == "doc-xyz-789"
        assert doc_body["page_number"] == 2
        assert len(doc_body["embedding"]) == 384

    @patch("backend.app.services.search.helpers.bulk")
    @patch("backend.app.services.search.Elasticsearch")
    def test_bulk_indexing_helpers_integration(self, mock_es_class, mock_bulk):
        """[Mocked Unit Test] Verify helpers.bulk execution."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True
        mock_es_class.return_value = mock_client
        mock_bulk.return_value = (3, [])

        provider = ElasticsearchProvider()
        doc = Document(id="doc-1", filename="f1.pdf", document_type="invoice", version=1)
        items = [
            (DocumentChunk(id=f"c-{i}", document_id="doc-1", chunk_index=i, start_char=0, end_char=10, page_number=1, content=f"text {i}"), doc, [0.1]*384)
            for i in range(3)
        ]

        success, failed, failed_ids = provider.bulk_index_chunks(items)
        assert success == 3
        assert failed == 0
        assert failed_ids == []
        mock_bulk.assert_called_once()

    @patch("backend.app.services.search.helpers.bulk")
    @patch("backend.app.services.search.Elasticsearch")
    def test_bulk_indexing_partial_failure_tracking(self, mock_es_class, mock_bulk):
        """[Mocked Unit Test] Verify partial failure correctly tracks failed chunk IDs."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True
        mock_es_class.return_value = mock_client
        mock_bulk.return_value = (
            2,
            [{"index": {"_id": "c-2", "status": 400, "error": {"type": "mapper_parsing_exception"}}}]
        )

        provider = ElasticsearchProvider()
        doc = Document(id="doc-1", filename="f1.pdf", document_type="invoice", version=1)
        items = [
            (DocumentChunk(id=f"c-{i}", document_id="doc-1", chunk_index=i, start_char=0, end_char=10, page_number=1, content=f"text {i}"), doc, [0.1]*384)
            for i in range(3)
        ]

        success, failed, failed_ids = provider.bulk_index_chunks(items)
        assert success == 2
        assert failed == 1
        assert failed_ids == ["c-2"]

    @patch("backend.app.services.search.Elasticsearch")
    def test_document_deletion_propagation_via_delete_by_query(self, mock_es_class):
        """[Mocked Unit Test] Verify document deletion purges all document chunks in ES."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.delete_by_query.return_value = {"deleted": 4}
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        deleted_count = provider.delete_document_chunks("doc-delete-target-999")

        assert deleted_count == 4
        mock_client.delete_by_query.assert_called_once()
        call_kwargs = mock_client.delete_by_query.call_args[1]
        assert call_kwargs["index"] == provider.index_name
        assert call_kwargs["query"] == {"term": {"document_id": "doc-delete-target-999"}}


class TestReconciliationLogic:
    """Verifies reconciliation detects missing, orphaned, and stale records between DB and ES."""

    @patch("backend.app.services.search.Elasticsearch")
    def test_reconciliation_detects_missing_and_orphaned_chunks(self, mock_es_class):
        """[Mocked Unit Test] DB has chunks 1 & 2; ES has chunks 2 & 3. Missing: 1, Orphaned: 3."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True
        # ES returns chunks c-2 and c-3
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"chunk_id": "c-2", "document_id": "d-1", "version": 1}},
                    {"_source": {"chunk_id": "c-3", "document_id": "d-old", "version": 1}}
                ]
            }
        }
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        mock_db = MagicMock()
        # DB has chunks c-1 and c-2
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("c-1", "d-1", 1),
            ("c-2", "d-1", 1)
        ]

        report = provider.reconcile_index(mock_db)

        assert report["reconciled"] is False
        assert report["missing_in_es"] == ["c-1"]
        assert report["orphaned_in_es"] == ["c-3"]
        assert report["missing_count"] == 1
        assert report["orphaned_count"] == 1

    @patch("backend.app.services.search.Elasticsearch")
    def test_reconciliation_when_in_sync(self, mock_es_class):
        """[Mocked Unit Test] Verify clean reconciliation report when DB and ES match."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"chunk_id": "c-1", "document_id": "d-1", "version": 1}},
                    {"_source": {"chunk_id": "c-2", "document_id": "d-1", "version": 1}}
                ]
            }
        }
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        mock_db = MagicMock()
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("c-1", "d-1", 1),
            ("c-2", "d-1", 1)
        ]

        report = provider.reconcile_index(mock_db)
        assert report["reconciled"] is True
        assert report["missing_count"] == 0
        assert report["orphaned_count"] == 0

    @patch("backend.app.services.search.Elasticsearch")
    def test_reconciliation_pruning_orphans(self, mock_es_class):
        """[Mocked Unit Test] Verify prune_orphans=True deletes orphaned chunks."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.indices.exists.return_value = True
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"chunk_id": "c-valid", "document_id": "d-1", "version": 1}},
                    {"_source": {"chunk_id": "c-orphan-1", "document_id": "d-deleted", "version": 1}}
                ]
            }
        }
        mock_client.delete.return_value = {"result": "deleted"}
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        mock_db = MagicMock()
        mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [
            ("c-valid", "d-1", 1)
        ]

        report = provider.reconcile_index(mock_db, prune_orphans=True)
        assert report["orphaned_count"] == 1
        assert report["pruned_orphans_count"] == 1
        mock_client.delete.assert_called_once_with(index=provider.index_name, id="c-orphan-1", ignore=[404])


class TestResilienceAndFallbackBehavior:
    """Verifies that offline or timing-out Elasticsearch safely falls back without downtime."""

    def test_es_unavailable_falls_back_cleanly_to_local_provider(self):
        """When ES is offline, SearchService must serve requests via local_search_engine."""
        service = SearchService()
        # Force ES unavailable
        service.es_provider.is_available = MagicMock(return_value=False)

        active_provider, name = service.get_active_provider()
        assert name == "local_search_engine"
        assert isinstance(active_provider, LocalSearchProvider)

    @patch("backend.app.services.search.Elasticsearch")
    def test_cluster_info_reports_unreachable_when_offline(self, mock_es_class):
        mock_client = MagicMock()
        mock_client.ping.return_value = False
        mock_es_class.return_value = mock_client

        provider = ElasticsearchProvider()
        info = provider.get_cluster_info()

        assert info["connected"] is False
        assert info["status"] == "unreachable"

    def test_local_provider_empty_results_safe_return(self):
        mock_db = MagicMock()
        mock_db.query.return_value.join.return_value.all.return_value = []

        local_provider = LocalSearchProvider()
        results, label = local_provider.search(query="nonexistent query", db=mock_db)
        assert results == []
        assert "local_search_engine" in label


class TestLiveClusterConnectivity:
    """Checks live cluster connectivity on port 9200 and explicitly classifies status."""

    def test_check_live_cluster_presence(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            res = s.connect_ex(("127.0.0.1", 9200))
            is_live = (res == 0)
        finally:
            s.close()

        if is_live:
            provider = ElasticsearchProvider()
            assert provider.is_available() is True
            info = provider.get_cluster_info()
            assert info["connected"] is True
            print(f"[LIVE INTEGRATION PASS] Connected to real Elasticsearch: {info.get('elasticsearch_version')}")
        else:
            pytest.skip("No live Elasticsearch instance listening on port 9200. Live integration tests marked as BLOCKED.")
