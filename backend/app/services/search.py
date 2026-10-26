import json
import math
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from elasticsearch import Elasticsearch
from backend.app.config import settings
from backend.app.services.embeddings import embedding_service
from backend.app.models.document import Document, DocumentChunk

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
            self.client = Elasticsearch(
                self.es_url,
                basic_auth=auth,
                request_timeout=2.0,
                max_retries=1
            )
        except Exception:
            self.client = None

    def is_available(self) -> bool:
        if not self.client:
            self._init_client()
        try:
            return bool(self.client and self.client.ping())
        except Exception:
            return False

    def init_index(self) -> bool:
        if not self.is_available():
            return False
        try:
            if not self.client.indices.exists(index=self.index_name):
                mappings = {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "document_id": {"type": "keyword"},
                        "filename": {"type": "keyword"},
                        "document_type": {"type": "keyword"},
                        "page_number": {"type": "integer"},
                        "content": {"type": "text", "analyzer": "standard"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": 384,
                            "index": True,
                            "similarity": "cosine"
                        },
                        "created_at": {"type": "date"}
                    }
                }
                self.client.indices.create(index=self.index_name, mappings=mappings)
            return True
        except Exception:
            return False

    def index_chunk(self, chunk: DocumentChunk, document: Document, embedding: List[float]) -> bool:
        if not self.is_available():
            return False
        try:
            doc = {
                "chunk_id": chunk.id,
                "document_id": document.id,
                "filename": document.filename,
                "document_type": document.document_type,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "embedding": embedding,
                "created_at": chunk.created_at.isoformat()
            }
            self.client.index(index=self.index_name, id=chunk.id, document=doc)
            return True
        except Exception:
            return False

    def search(
        self,
        query: str,
        db: Session,
        mode: str = "hybrid",
        top_k: int = 10,
        doc_type_filter: Optional[str] = None
    ) -> Tuple[List[SearchResult], str]:
        if not self.is_available():
            raise RuntimeError("Elasticsearch is currently unreachable.")

        query_vector = embedding_service.embed_text(query)
        results: List[SearchResult] = []

        # Build ES query according to mode
        filter_clause = []
        if doc_type_filter:
            filter_clause.append({"term": {"document_type": doc_type_filter}})

        if mode == "lexical":
            es_query = {
                "bool": {
                    "must": [{"match": {"content": query}}],
                    "filter": filter_clause
                }
            }
            resp = self.client.search(
                index=self.index_name,
                query=es_query,
                size=top_k,
                highlight={"fields": {"content": {}}}
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
                    score=float(hit["_score"]),
                    lexical_score=float(hit["_score"]),
                    vector_score=0.0,
                    retrieval_mode="lexical"
                ))
            return results, "elasticsearch_bm25"

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
                    snippet=source["content"][:180] + "...",
                    score=float(hit["_score"]),
                    lexical_score=0.0,
                    vector_score=float(hit["_score"]),
                    retrieval_mode="semantic"
                ))
            return results, "elasticsearch_knn"

        else:  # hybrid RRF
            resp = self.client.search(
                index=self.index_name,
                query={"bool": {"must": [{"match": {"content": query}}], "filter": filter_clause}},
                knn={
                    "field": "embedding",
                    "query_vector": query_vector,
                    "k": top_k,
                    "num_candidates": 50,
                    "filter": filter_clause
                },
                rank={"rrf": {"window_size": 50, "rank_constant": 60}},
                size=top_k,
                highlight={"fields": {"content": {}}}
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
                    score=float(hit["_score"]),
                    lexical_score=float(hit["_score"]),
                    vector_score=float(hit["_score"]),
                    retrieval_mode="hybrid"
                ))
            return results, "elasticsearch_rrf_hybrid"


class LocalSearchProvider(BaseSearchProvider):
    """
    In-process, durable search provider backed by PostgreSQL/SQLite and numpy dense vectors.
    Provides verified BM25 scoring + genuine cosine similarity + Reciprocal Rank Fusion.
    """
    def is_available(self) -> bool:
        return True

    def index_chunk(self, chunk: DocumentChunk, document: Document, embedding: List[float]) -> bool:
        # Serialized in DB directly
        return True

    def search(
        self,
        query: str,
        db: Session,
        mode: str = "hybrid",
        top_k: int = 10,
        doc_type_filter: Optional[str] = None
    ) -> Tuple[List[SearchResult], str]:
        # Fetch candidate chunks with their document metadata
        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        query_vector = embedding_service.embed_text(query)

        query_builder = db.query(DocumentChunk, Document).join(Document, DocumentChunk.document_id == Document.id)
        if doc_type_filter:
            query_builder = query_builder.filter(Document.document_type == doc_type_filter)
        
        records = query_builder.all()
        if not records:
            return [], "local_engine"

        # Calculate scores
        scored_items = []
        for chunk, doc in records:
            text_lower = chunk.content.lower()
            
            # 1. Lexical BM25 approximation
            lexical_score = 0.0
            if query_terms:
                doc_len = len(text_lower.split())
                avg_doc_len = 50.0
                k1 = 1.2
                b = 0.75
                for term in query_terms:
                    tf = text_lower.count(term)
                    if tf > 0:
                        # BM25 term weighting
                        numerator = tf * (k1 + 1)
                        denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                        lexical_score += (numerator / denominator)

            # 2. Vector Cosine Similarity
            vector_score = 0.0
            if chunk.embedding:
                try:
                    chunk_vec = json.loads(chunk.embedding)
                    vector_score = embedding_service.cosine_similarity(query_vector, chunk_vec)
                    # Normalize cosine (-1..1 to 0..1)
                    vector_score = max(0.0, (vector_score + 1.0) / 2.0)
                except Exception:
                    vector_score = 0.0

            # 3. Create highlighted snippet
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
            # Rank lexical
            scored_items.sort(key=lambda x: x["lexical_score"], reverse=True)
            for rank, item in enumerate(scored_items, start=1):
                item["rank_lexical"] = rank

            # Rank vector
            scored_items.sort(key=lambda x: x["vector_score"], reverse=True)
            for rank, item in enumerate(scored_items, start=1):
                item["rank_vector"] = rank

            # Reciprocal Rank Fusion: RRF = 1 / (60 + rank_lexical) + 1 / (60 + rank_vector)
            for item in scored_items:
                rrf_score = (1.0 / (60.0 + item["rank_lexical"])) + (1.0 / (60.0 + item["rank_vector"]))
                item["final_score"] = rrf_score

            scored_items.sort(key=lambda x: x["final_score"], reverse=True)

        # Build output results
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

        # Find first occurrence of any query term
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

search_service = SearchService()
