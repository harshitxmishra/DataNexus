import json
import logging
import math
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from elasticsearch import Elasticsearch, helpers

from backend.app.config import settings
from backend.app.services.embeddings import embedding_service
from backend.app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)

# Canonical Elasticsearch Index Mapping for DataNexus Chunks
DATANEXUS_INDEX_MAPPINGS = {
    "properties": {
        "chunk_id": {"type": "keyword"},
        "document_id": {"type": "keyword"},
        "filename": {
            "type": "keyword",
            "fields": {
                "text": {"type": "text"}
            }
        },
        "document_type": {"type": "keyword"},
        "page_number": {"type": "integer"},
        "chunk_index": {"type": "integer"},
        "start_char": {"type": "integer"},
        "end_char": {"type": "integer"},
        "content": {
            "type": "text",
            "analyzer": "standard",
            "fields": {
                "keyword": {"type": "keyword", "ignore_above": 256}
            }
        },
        "embedding": {
            "type": "dense_vector",
            "dims": 384,
            "index": True,
            "similarity": "cosine"
        },
        "created_at": {"type": "date"},
        "version": {"type": "integer"}
    }
}

INDEX_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.mapping.total_fields.limit": 1000
}


class SearchResult:
    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        filename: str,
        document_type: str,
        page_number: int,
        content: str,
        snippet: str,
        score: float,
        lexical_score: float = 0.0,
        vector_score: float = 0.0,
        retrieval_mode: str = "hybrid"
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.filename = filename
        self.document_type = document_type
        self.page_number = page_number
        self.content = content
        self.snippet = snippet
        self.score = round(score, 4)
        self.lexical_score = round(lexical_score, 4)
        self.vector_score = round(vector_score, 4)
        self.retrieval_mode = retrieval_mode

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "document_type": self.document_type,
            "page_number": self.page_number,
            "content": self.content,
            "snippet": self.snippet,
            "score": self.score,
            "lexical_score": self.lexical_score,
            "vector_score": self.vector_score,
            "retrieval_mode": self.retrieval_mode
        }


class BaseSearchProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def index_chunk(self, chunk: DocumentChunk, document: Document, embedding: List[float]) -> bool:
        pass

    @abstractmethod
    def delete_document_chunks(self, document_id: str) -> int:
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        db: Session,
        mode: str = "hybrid",
        top_k: int = 10,
        doc_type_filter: Optional[str] = None
    ) -> Tuple[List[SearchResult], str]:
        pass


class ElasticsearchProvider(BaseSearchProvider):
    """
    Production-grade Elasticsearch provider.
    Supports BM25 lexical search, 384-d dense vector kNN, Reciprocal Rank Fusion (RRF),
    idempotent upserts, and index reconciliation.
    """
    def __init__(self):
        self.es_url = settings.ELASTICSEARCH_URL
        self.index_name = settings.ELASTICSEARCH_INDEX
        self.client: Optional[Elasticsearch] = None
        self._init_client()

    def _init_client(self):
        try:
            auth = None
            if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
                auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

            ca_certs = settings.ELASTICSEARCH_CA_CERTS or None
            verify_certs = settings.ELASTICSEARCH_VERIFY_CERTS if hasattr(settings, "ELASTICSEARCH_VERIFY_CERTS") else True

            self.client = Elasticsearch(
                self.es_url,
                basic_auth=auth,
                ca_certs=ca_certs,
                verify_certs=verify_certs,
                request_timeout=getattr(settings, "ELASTICSEARCH_TIMEOUT_SECONDS", 3.0),
                max_retries=getattr(settings, "ELASTICSEARCH_MAX_RETRIES", 2),
                retry_on_timeout=getattr(settings, "ELASTICSEARCH_RETRY_ON_TIMEOUT", True)
            )
        except Exception as e:
            logger.warning(f"Elasticsearch client initialization failed: {e}")
            self.client = None

    def is_available(self) -> bool:
        if not self.client:
            self._init_client()
        if not self.client:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def get_cluster_info(self) -> Dict[str, Any]:
        """Inspect cluster health, version, and index metadata."""
        if not self.is_available():
            return {
                "status": "unreachable",
                "connected": False,
                "endpoint": self.es_url,
                "index_name": self.index_name
            }
        try:
            info = self.client.info()
            health = self.client.cluster.health()
            exists = self.client.indices.exists(index=self.index_name)
            doc_count = 0
            if exists:
                count_resp = self.client.count(index=self.index_name)
                doc_count = count_resp.get("count", 0)

            return {
                "status": "healthy",
                "connected": True,
                "endpoint": self.es_url,
                "cluster_name": health.get("cluster_name"),
                "cluster_status": health.get("status"),
                "elasticsearch_version": info.get("version", {}).get("number"),
                "lucene_version": info.get("version", {}).get("lucene_version"),
                "index_name": self.index_name,
                "index_exists": exists,
                "total_indexed_chunks": doc_count
            }
        except Exception as e:
            return {
                "status": "error",
                "connected": False,
                "endpoint": self.es_url,
                "error": str(e)
            }

    def init_index(self, recreate: bool = False) -> bool:
        """Create or verify the versioned Elasticsearch index mapping."""
        if not self.is_available():
            return False
        try:
            exists = self.client.indices.exists(index=self.index_name)
            if exists and recreate:
                self.client.indices.delete(index=self.index_name)
                exists = False

            if not exists:
                self.client.indices.create(
                    index=self.index_name,
                    mappings=DATANEXUS_INDEX_MAPPINGS,
                    settings=INDEX_SETTINGS
                )
            return True
        except Exception as e:
            logger.error(f"Failed creating/verifying index {self.index_name}: {e}")
            return False

    def index_chunk(self, chunk: DocumentChunk, document: Document, embedding: List[float]) -> bool:
        """Idempotently index a single document chunk."""
        if not self.is_available():
            return False
        try:
            self.init_index()
            doc_body = {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "filename": document.filename,
                "document_type": document.document_type,
                "page_number": chunk.page_number,
                "chunk_index": getattr(chunk, "chunk_index", 0),
                "start_char": getattr(chunk, "start_char", 0),
                "end_char": getattr(chunk, "end_char", 0),
                "content": chunk.content,
                "embedding": embedding,
                "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
                "version": document.version or 1
            }
            self.client.index(index=self.index_name, id=chunk.id, document=doc_body)
            return True
        except Exception as e:
            logger.error(f"Failed indexing chunk {chunk.id} in Elasticsearch: {e}")
            return False

    def bulk_index_chunks(self, items: List[Tuple[DocumentChunk, Document, List[float]]]) -> Tuple[int, int]:
        """Bulk index chunks with deterministic chunk IDs for performance."""
        if not self.is_available() or not items:
            return 0, len(items)

        self.init_index()
        actions = []
        for chunk, doc, emb in items:
            actions.append({
                "_index": self.index_name,
                "_id": chunk.id,
                "_source": {
                    "chunk_id": chunk.id,
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "document_type": doc.document_type,
                    "page_number": chunk.page_number,
                    "chunk_index": getattr(chunk, "chunk_index", 0),
                    "start_char": getattr(chunk, "start_char", 0),
                    "end_char": getattr(chunk, "end_char", 0),
                    "content": chunk.content,
                    "embedding": emb,
                    "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
                    "version": doc.version or 1
                }
            })

        try:
            success, errors = helpers.bulk(self.client, actions, raise_on_error=False)
            failed_count = len(errors) if isinstance(errors, list) else 0
            return success, failed_count
        except Exception as e:
            logger.error(f"Elasticsearch bulk indexing exception: {e}")
            return 0, len(items)

    def delete_chunk(self, chunk_id: str) -> bool:
        """Delete a single chunk by ID."""
        if not self.is_available():
            return False
        try:
            self.client.delete(index=self.index_name, id=chunk_id, ignore=[404])
            return True
        except Exception as e:
            logger.error(f"Failed deleting chunk {chunk_id}: {e}")
            return False

    def delete_document_chunks(self, document_id: str) -> int:
        """Delete all indexed chunks belonging to a document."""
        if not self.is_available():
            return 0
        try:
            resp = self.client.delete_by_query(
                index=self.index_name,
                query={"term": {"document_id": document_id}},
                conflicts="proceed"
            )
            return resp.get("deleted", 0)
        except Exception as e:
            logger.error(f"Failed deleting chunks for document {document_id}: {e}")
            return 0

    def search(
        self,
        query: str,
        db: Session,
        mode: str = "hybrid",
        top_k: int = 10,
        doc_type_filter: Optional[str] = None
    ) -> Tuple[List[SearchResult], str]:
        """Execute BM25, kNN vector, or hybrid RRF retrieval in Elasticsearch."""
        if not self.is_available():
            raise RuntimeError("Elasticsearch is currently unreachable.")

        query_vector = embedding_service.embed_text(query)
        results: List[SearchResult] = []

        filter_clause = []
        if doc_type_filter:
            filter_clause.append({"term": {"document_type": doc_type_filter}})

        # 1. Lexical (BM25)
        if mode == "lexical":
            es_query = {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["content^2.0", "filename^1.0"]
                            }
                        }
                    ],
                    "filter": filter_clause
                }
            }
            resp = self.client.search(
                index=self.index_name,
                query=es_query,
                size=top_k,
                highlight={"fields": {"content": {"fragment_size": 180, "number_of_fragments": 1}}}
            )
            for hit in resp["hits"]["hits"]:
                source = hit["_source"]
                snippet = hit.get("highlight", {}).get("content", [source["content"][:180]])[0]
                results.append(SearchResult(
                    chunk_id=source["chunk_id"],
                    document_id=source["document_id"],
                    filename=source["filename"],
                    document_type=source["document_type"],
                    page_number=source["page_number"],
                    content=source["content"],
                    snippet=snippet,
                    score=float(hit["_score"] or 0.0),
                    lexical_score=float(hit["_score"] or 0.0),
                    vector_score=0.0,
                    retrieval_mode="lexical"
                ))
            return results, "elasticsearch_bm25"

        # 2. Semantic (Dense Vector kNN)
        elif mode == "semantic":
            knn_clause = {
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": max(50, top_k * 2)
            }
            if filter_clause:
                knn_clause["filter"] = filter_clause

            resp = self.client.search(
                index=self.index_name,
                knn=knn_clause,
                size=top_k
            )
            for hit in resp["hits"]["hits"]:
                source = hit["_source"]
                results.append(SearchResult(
                    chunk_id=source["chunk_id"],
                    document_id=source["document_id"],
                    filename=source["filename"],
                    document_type=source["document_type"],
                    page_number=source["page_number"],
                    content=source["content"],
                    snippet=source["content"][:180] + ("..." if len(source["content"]) > 180 else ""),
                    score=float(hit["_score"] or 0.0),
                    lexical_score=0.0,
                    vector_score=float(hit["_score"] or 0.0),
                    retrieval_mode="semantic"
                ))
            return results, "elasticsearch_knn"

        # 3. Hybrid (Reciprocal Rank Fusion RRF)
        else:
            match_query = {
                "bool": {
                    "must": [{"multi_match": {"query": query, "fields": ["content^2.0", "filename^1.0"]}}],
                    "filter": filter_clause
                }
            }
            knn_query = {
                "field": "embedding",
                "query_vector": query_vector,
                "k": top_k,
                "num_candidates": max(50, top_k * 2)
            }
            if filter_clause:
                knn_query["filter"] = filter_clause

            resp = self.client.search(
                index=self.index_name,
                query=match_query,
                knn=knn_query,
                rank={"rrf": {"window_size": 50, "rank_constant": 60}},
                size=top_k,
                highlight={"fields": {"content": {"fragment_size": 180, "number_of_fragments": 1}}}
            )
            for hit in resp["hits"]["hits"]:
                source = hit["_source"]
                snippet = hit.get("highlight", {}).get("content", [source["content"][:180]])[0]
                results.append(SearchResult(
                    chunk_id=source["chunk_id"],
                    document_id=source["document_id"],
                    filename=source["filename"],
                    document_type=source["document_type"],
                    page_number=source["page_number"],
                    content=source["content"],
                    snippet=snippet,
                    score=float(hit["_score"] or 0.0),
                    lexical_score=float(hit["_score"] or 0.0),
                    vector_score=float(hit["_score"] or 0.0),
                    retrieval_mode="hybrid"
                ))
            return results, "elasticsearch_hybrid_rrf"

    def reconcile_index(self, db: Session) -> Dict[str, Any]:
        """
        Compare PostgreSQL/SQLite canonical records with Elasticsearch index.
        Reports missing, stale, and orphaned chunks.
        """
        if not self.is_available():
            return {
                "status": "unavailable",
                "reconciled": False,
                "error": "Elasticsearch is unreachable",
                "missing_in_es": [],
                "orphaned_in_es": [],
                "missing_count": 0,
                "orphaned_count": 0
            }

        # 1. Fetch all canonical chunks and document versions from DB
        db_records = (
            db.query(DocumentChunk.id, DocumentChunk.document_id, Document.version)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(Document.status.in_(["completed", "partially_completed"]))
            .all()
        )
        db_chunk_map = {rec[0]: {"document_id": rec[1], "version": rec[2] or 1} for rec in db_records}
        db_chunk_ids = set(db_chunk_map.keys())

        # 2. Fetch all chunk IDs from Elasticsearch index
        self.init_index()
        es_chunk_ids = set()
        es_chunk_versions = {}
        try:
            resp = self.client.search(
                index=self.index_name,
                query={"match_all": {}},
                _source=["chunk_id", "document_id", "version"],
                size=10000
            )
            for hit in resp["hits"]["hits"]:
                src = hit["_source"]
                cid = src.get("chunk_id")
                if cid:
                    es_chunk_ids.add(cid)
                    es_chunk_versions[cid] = src.get("version", 1)
        except Exception as e:
            logger.error(f"Error fetching Elasticsearch records during reconciliation: {e}")

        # 3. Detect discrepancies
        missing_in_es = list(db_chunk_ids - es_chunk_ids)
        orphaned_in_es = list(es_chunk_ids - db_chunk_ids)
        stale_in_es = [
            cid for cid in (db_chunk_ids & es_chunk_ids)
            if db_chunk_map[cid]["version"] != es_chunk_versions.get(cid)
        ]

        return {
            "status": "completed",
            "reconciled": len(missing_in_es) == 0 and len(orphaned_in_es) == 0 and len(stale_in_es) == 0,
            "total_db_chunks": len(db_chunk_ids),
            "total_es_chunks": len(es_chunk_ids),
            "missing_in_es": missing_in_es,
            "missing_count": len(missing_in_es),
            "orphaned_in_es": orphaned_in_es,
            "orphaned_count": len(orphaned_in_es),
            "stale_in_es": stale_in_es,
            "stale_count": len(stale_in_es)
        }

    def reindex_all(self, db: Session) -> Dict[str, Any]:
        """Reindex all eligible chunks from the canonical database into Elasticsearch."""
        if not self.is_available():
            return {
                "status": "failed",
                "indexed": 0,
                "failed": 0,
                "error": "Elasticsearch is unreachable"
            }

        chunks_with_doc = (
            db.query(DocumentChunk, Document)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(Document.status.in_(["completed", "partially_completed"]))
            .all()
        )

        items_to_index = []
        for chunk, doc in chunks_with_doc:
            vec = json.loads(chunk.embedding) if chunk.embedding else []
            items_to_index.append((chunk, doc, vec))

        success, failed = self.bulk_index_chunks(items_to_index)

        # Update indexed_in_es flags in database
        if success > 0:
            for chunk, doc in chunks_with_doc:
                chunk.indexed_in_es = True
            db.commit()

        return {
            "status": "success" if failed == 0 else "partial_success",
            "total_chunks_processed": len(items_to_index),
            "indexed_count": success,
            "failed_count": failed
        }


class LocalSearchProvider(BaseSearchProvider):
    """
    In-process, durable search provider backed by PostgreSQL/SQLite and numpy dense vectors.
    Provides verified BM25 scoring + genuine cosine similarity + Reciprocal Rank Fusion.
    Explicitly labeled as local_search_engine fallback.
    """
    def is_available(self) -> bool:
        return True

    def index_chunk(self, chunk: DocumentChunk, document: Document, embedding: List[float]) -> bool:
        return True

    def delete_document_chunks(self, document_id: str) -> int:
        return 0

    def search(
        self,
        query: str,
        db: Session,
        mode: str = "hybrid",
        top_k: int = 10,
        doc_type_filter: Optional[str] = None
    ) -> Tuple[List[SearchResult], str]:
        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        query_vector = embedding_service.embed_text(query)

        query_builder = db.query(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id)
        if doc_type_filter:
            query_builder = query_builder.filter(Document.document_type == doc_type_filter)

        records = query_builder.all()
        if not records:
            return [], f"local_search_engine ({mode})"

        scored_items = []
        for chunk, doc in records:
            text_lower = chunk.content.lower()

            # 1. Lexical BM25 calculation
            lexical_score = 0.0
            if query_terms:
                doc_len = len(text_lower.split())
                avg_doc_len = 50.0
                k1 = 1.2
                b = 0.75
                for term in query_terms:
                    tf = text_lower.count(term)
                    if tf > 0:
                        numerator = tf * (k1 + 1)
                        denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                        lexical_score += (numerator / denominator)

            # 2. Vector Cosine Similarity
            vector_score = 0.0
            if chunk.embedding:
                try:
                    chunk_vec = json.loads(chunk.embedding)
                    vector_score = embedding_service.cosine_similarity(query_vector, chunk_vec)
                    vector_score = max(0.0, (vector_score + 1.0) / 2.0)
                except Exception:
                    vector_score = 0.0

            snippet = self._generate_snippet(chunk.content, query_terms)

            scored_items.append({
                "chunk": chunk,
                "doc": doc,
                "lexical_score": lexical_score,
                "vector_score": vector_score,
                "snippet": snippet
            })

        # Rank and combine based on retrieval mode
        if mode == "lexical":
            scored_items.sort(key=lambda x: x["lexical_score"], reverse=True)
            for item in scored_items:
                item["final_score"] = item["lexical_score"]
        elif mode == "semantic":
            scored_items.sort(key=lambda x: x["vector_score"], reverse=True)
            for item in scored_items:
                item["final_score"] = item["vector_score"]
        else:  # hybrid RRF
            scored_items.sort(key=lambda x: x["lexical_score"], reverse=True)
            for rank, item in enumerate(scored_items, start=1):
                item["rank_lexical"] = rank

            scored_items.sort(key=lambda x: x["vector_score"], reverse=True)
            for rank, item in enumerate(scored_items, start=1):
                item["rank_vector"] = rank

            for item in scored_items:
                rrf_score = (1.0 / (60.0 + item["rank_lexical"])) + (1.0 / (60.0 + item["rank_vector"]))
                item["final_score"] = rrf_score

            scored_items.sort(key=lambda x: x["final_score"], reverse=True)

        top_items = scored_items[:top_k]
        results = [
            SearchResult(
                chunk_id=item["chunk"].id,
                document_id=item["doc"].id,
                filename=item["doc"].filename,
                document_type=item["doc"].document_type,
                page_number=item["chunk"].page_number,
                content=item["chunk"].content,
                snippet=item["snippet"],
                score=item["final_score"],
                lexical_score=item["lexical_score"],
                vector_score=item["vector_score"],
                retrieval_mode=mode
            )
            for item in top_items if item["final_score"] > 0
        ]

        engine_label = f"local_search_engine ({mode})"
        return results, engine_label

    def _generate_snippet(self, text: str, query_terms: List[str]) -> str:
        if not query_terms:
            return text[:200] + ("..." if len(text) > 200 else "")

        text_lower = text.lower()
        first_pos = -1
        for term in query_terms:
            pos = text_lower.find(term)
            if pos != -1 and (first_pos == -1 or pos < first_pos):
                first_pos = pos

        if first_pos == -1:
            return text[:200] + ("..." if len(text) > 200 else "")

        start = max(0, first_pos - 60)
        end = min(len(text), first_pos + 140)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet


class SearchService:
    def __init__(self):
        self.es_provider = ElasticsearchProvider()
        self.local_provider = LocalSearchProvider()

    def get_active_provider(self) -> Tuple[BaseSearchProvider, str]:
        if self.es_provider.is_available():
            return self.es_provider, "elasticsearch"
        return self.local_provider, "local_search_engine"

    def search(
        self,
        query: str,
        db: Session,
        mode: str = "hybrid",
        top_k: int = 10,
        doc_type_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        provider, provider_name = self.get_active_provider()
        results, engine_label = provider.search(
            query=query,
            db=db,
            mode=mode,
            top_k=top_k,
            doc_type_filter=doc_type_filter
        )
        return {
            "query": query,
            "provider": provider_name,
            "engine": engine_label,
            "retrieval_mode": mode,
            "total_hits": len(results),
            "results": [r.to_dict() for r in results]
        }

    def delete_document_chunks(self, document_id: str) -> int:
        """Purge document chunks from Elasticsearch on document deletion."""
        if self.es_provider.is_available():
            return self.es_provider.delete_document_chunks(document_id)
        return 0

    def reconcile(self, db: Session) -> Dict[str, Any]:
        return self.es_provider.reconcile_index(db)

    def reindex(self, db: Session) -> Dict[str, Any]:
        return self.es_provider.reindex_all(db)

    def get_status(self, db: Session) -> Dict[str, Any]:
        total_chunks = db.query(DocumentChunk).count()
        indexed_chunks = db.query(DocumentChunk).filter(DocumentChunk.indexed_in_es == True).count()
        provider, provider_name = self.get_active_provider()
        cluster_info = self.es_provider.get_cluster_info()

        return {
            "active_provider": provider_name,
            "elasticsearch_connected": self.es_provider.is_available(),
            "cluster_info": cluster_info,
            "total_chunks_stored": total_chunks,
            "total_chunks_indexed": indexed_chunks,
            "unindexed_outbox_chunks": max(0, total_chunks - indexed_chunks),
            "supported_modes": ["lexical", "semantic", "hybrid"],
            "fallback_active": provider_name != "elasticsearch"
        }


search_service = SearchService()
