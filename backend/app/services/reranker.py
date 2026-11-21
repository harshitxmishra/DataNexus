"""
DataNexus v2.0.0 — FlashRank Cross-Encoder Reranker Service.

Two-stage retrieval: after BM25/kNN/hybrid RRF first-stage retrieval,
applies a cross-encoder reranker (ms-marco-MiniLM-L-12-v2, CPU/ONNX)
to rescore and reorder results for precision.

Gated behind RERANKER_ENABLED config flag for A/B benchmarking.
"""

import logging
from typing import List, Dict, Any, Optional

from backend.app.config import settings

logger = logging.getLogger(__name__)


class RerankerService:
    """
    CPU-only ONNX cross-encoder reranker using FlashRank.
    Lazy-loaded to avoid import cost when disabled.
    """

    def __init__(self):
        self._ranker = None
        self._initialized = False
        self._available = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        self._initialized = True

        if not getattr(settings, "RERANKER_ENABLED", True):
            logger.info("Reranker disabled by RERANKER_ENABLED=false")
            self._available = False
            return

        try:
            from flashrank import Ranker
            model_name = getattr(settings, "RERANKER_MODEL", "ms-marco-MiniLM-L-12-v2")
            cache_dir = getattr(settings, "RERANKER_CACHE_DIR", "")
            if cache_dir and str(cache_dir).strip():
                self._ranker = Ranker(model_name=model_name, cache_dir=str(cache_dir).strip())
            else:
                self._ranker = Ranker(model_name=model_name)
            self._available = True
            logger.info(f"FlashRank reranker initialized: model={model_name}")
        except ImportError:
            logger.warning("flashrank package not installed — reranker unavailable")
            self._available = False
        except Exception as e:
            logger.warning(f"FlashRank reranker initialization failed: {e}")
            self._available = False

    @property
    def is_enabled(self) -> bool:
        return getattr(settings, "RERANKER_ENABLED", True)

    @property
    def is_available(self) -> bool:
        self._ensure_initialized()
        return self._available

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank search results using cross-encoder scoring.
        
        Args:
            query: Original search query
            results: List of search result dicts (must have 'content' key)
            top_k: Max results to return after reranking (None = return all)
            
        Returns:
            Reranked list of result dicts with added 'rerank_score' field
        """
        self._ensure_initialized()

        if not self._available or not results:
            return results

        try:
            from flashrank import RerankRequest

            # Build passages for FlashRank
            passages = []
            for r in results:
                passages.append({
                    "id": r.get("chunk_id", ""),
                    "text": r.get("content", ""),
                    "meta": r  # Preserve original result data
                })

            rerank_request = RerankRequest(query=query, passages=passages)
            reranked = self._ranker.rerank(rerank_request)

            # Rebuild result list from reranked passages
            reranked_results = []
            for rr in reranked:
                original = rr["meta"]
                original["rerank_score"] = round(float(rr["score"]), 4)
                reranked_results.append(original)

            if top_k:
                reranked_results = reranked_results[:top_k]

            return reranked_results

        except Exception as e:
            logger.warning(f"Reranking failed, returning original results: {e}")
            return results


reranker_service = RerankerService()
