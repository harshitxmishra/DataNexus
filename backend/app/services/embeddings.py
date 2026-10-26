import json
import logging
import threading
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sqlalchemy.orm import Session

from backend.app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingInferenceError(RuntimeError):
    """Raised when embedding model loading or inference fails."""
    pass


class InterimHashingEmbeddingService:
    """
    Deterministic interim 384-dimensional representation based on character/word n-grams
    and orthonormalized random projection. Kept as a comparative baseline and regression fallback.
    Explicitly labeled as Representation Version 1 (lexical projection, NOT neural).
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.model_name = "tfidf-l2-384"
        self.provider = "local_dense"
        self.representation_version = 1
        self.model_revision = "interim-hashing-v1"
        self.device = "cpu"

        # Fixed random projection matrix for consistent dimension reduction to 384
        rng = np.random.RandomState(42)
        proj = rng.randn(2048, self.dimension)
        q, _ = np.linalg.qr(proj)
        self._projection_matrix = q

        self._vectorizer = HashingVectorizer(
            n_features=2048,
            norm=None,
            alternate_sign=False,
            ngram_range=(1, 2)
        )

    def is_available(self) -> bool:
        return True

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "dimension": self.dimension,
            "representation_version": self.representation_version,
            "model_revision": self.model_revision,
            "device": self.device,
            "is_neural": False,
            "status": "operational"
        }

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            vec = np.zeros(self.dimension)
            vec[0] = 1.0
            return vec.tolist()

        sparse_vec = self._vectorizer.transform([text.strip()]).toarray()[0]
        dense_vec = np.dot(sparse_vec, self._projection_matrix)
        norm = np.linalg.norm(dense_vec)
        if norm > 1e-12:
            dense_vec = dense_vec / norm
        else:
            dense_vec[0] = 1.0

        return dense_vec.round(6).tolist()

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))


class PretrainedNeuralEmbeddingService:
    """
    Genuine Pretrained Neural Semantic Embedding Service using SentenceTransformer.
    Default Model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions).
    Explicitly labeled as Representation Version 2.
    """
    def __init__(
        self,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
        cache_dir: Optional[str] = None,
        representation_version: Optional[int] = None,
        model_revision: Optional[str] = None
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self.device = device or settings.EMBEDDING_DEVICE
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.cache_dir = cache_dir or (settings.EMBEDDING_CACHE_DIR if settings.EMBEDDING_CACHE_DIR else None)
        self.representation_version = representation_version or settings.EMBEDDING_REPRESENTATION_VERSION
        self.model_revision = model_revision or settings.EMBEDDING_MODEL_REVISION
        self.provider = "sentence_transformers"

        self._model = None
        self._lock = threading.Lock()
        self._init_error: Optional[str] = None

    def _get_model(self):
        """Lazy thread-safe singleton initialization of pretrained neural model."""
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading pretrained embedding model '{self.model_name}' on device '{self.device}'...")
                
                kwargs: Dict[str, Any] = {"device": self.device}
                if self.cache_dir:
                    kwargs["cache_folder"] = self.cache_dir
                if self.model_revision:
                    kwargs["revision"] = self.model_revision

                model = SentenceTransformer(self.model_name, **kwargs)
                if hasattr(model, "get_embedding_dimension"):
                    actual_dim = model.get_embedding_dimension()
                else:
                    actual_dim = model.get_sentence_embedding_dimension()
                if actual_dim != self.dimension:
                    raise EmbeddingInferenceError(
                        f"Model dimension mismatch: configured {self.dimension}, actual {actual_dim}"
                    )
                self._model = model
                self._init_error = None
                logger.info(f"Successfully loaded '{self.model_name}' (dim={self.dimension}, revision={self.model_revision}).")
                return self._model
            except Exception as e:
                self._init_error = str(e)
                logger.error(f"Failed to load sentence-transformers model '{self.model_name}': {e}")
                raise EmbeddingInferenceError(f"Failed to load embedding model '{self.model_name}': {e}") from e

    def is_available(self) -> bool:
        """Check whether the neural model is loaded or can be loaded without error."""
        try:
            self._get_model()
            return True
        except Exception:
            return False

    def get_metadata(self) -> Dict[str, Any]:
        """Return diagnostic metadata about the neural embedding service."""
        available = False
        try:
            self._get_model()
            available = True
        except Exception:
            available = False

        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "dimension": self.dimension,
            "representation_version": self.representation_version,
            "model_revision": self.model_revision,
            "device": self.device,
            "batch_size": self.batch_size,
            "is_neural": True,
            "normalized": True,
            "status": "operational" if available else "unavailable",
            "init_error": self._init_error
        }

    def embed_text(self, text: str) -> List[float]:
        """
        Generate a verified, unit-norm 384-dimensional dense semantic embedding.
        Rejects NaNs, Infs, and dimension mismatches.
        Never silently falls back to random or zero vectors.
        """
        if text is None or not isinstance(text, str):
            text = ""

        # SentenceTransformer encodes empty strings into valid unit-norm embeddings representing empty sequence
        model = self._get_model()
        try:
            vec = model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
        except Exception as e:
            logger.error(f"Neural embedding inference failed for input text: {e}")
            raise EmbeddingInferenceError(f"Neural embedding inference exception: {e}") from e

        # Validation: Dimensions
        if vec.shape != (self.dimension,):
            raise EmbeddingInferenceError(
                f"Embedding output dimension mismatch: expected ({self.dimension},), got {vec.shape}"
            )

        # Validation: Finite values (reject NaN or Inf)
        if not np.isfinite(vec).all():
            raise EmbeddingInferenceError("Embedding vector contains non-finite values (NaN or Inf).")

        # Validation: Enforce strict L2 unit-norm
        norm = float(np.linalg.norm(vec))
        if norm > 1e-12:
            if abs(norm - 1.0) > 1e-4:
                vec = vec / norm
        else:
            raise EmbeddingInferenceError("Embedding vector collapsed to zero norm.")

        return [round(float(x), 6) for x in vec]

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        """
        Batch-encode a list of texts into genuine semantic embeddings with dimension verification.
        """
        if not texts:
            return []

        clean_texts = [t if (t is not None and isinstance(t, str)) else "" for t in texts]
        eff_batch_size = batch_size or self.batch_size
        model = self._get_model()

        try:
            embeddings_arr = model.encode(
                clean_texts,
                batch_size=eff_batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False
            )
        except Exception as e:
            logger.error(f"Neural batch embedding inference failed: {e}")
            raise EmbeddingInferenceError(f"Neural batch embedding exception: {e}") from e

        if len(embeddings_arr.shape) != 2 or embeddings_arr.shape[1] != self.dimension:
            raise EmbeddingInferenceError(
                f"Batch embedding dimension mismatch: expected (*, {self.dimension}), got {embeddings_arr.shape}"
            )

        if not np.isfinite(embeddings_arr).all():
            raise EmbeddingInferenceError("Batch embedding contains non-finite values (NaN or Inf).")

        # Ensure unit normalization across all rows
        norms = np.linalg.norm(embeddings_arr, axis=1, keepdims=True)
        # Avoid divide by zero
        norms[norms < 1e-12] = 1.0
        embeddings_arr = embeddings_arr / norms

        return [[round(float(x), 6) for x in row] for row in embeddings_arr]

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two unit-normalized vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))


class EmbeddingService:
    """
    Primary Embedding Service Facade.
    Delegates to PretrainedNeuralEmbeddingService (sentence-transformers) or InterimHashingEmbeddingService.
    Provides representation versioning, batch re-embedding, and health metadata.
    """
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.provider_name = settings.EMBEDDING_PROVIDER

        if self.provider_name == "sentence_transformers":
            self._impl = PretrainedNeuralEmbeddingService(dimension=dimension)
        else:
            self._impl = InterimHashingEmbeddingService(dimension=dimension)

        self._interim_baseline = InterimHashingEmbeddingService(dimension=dimension)

    @property
    def model_name(self) -> str:
        return self._impl.model_name

    @property
    def provider(self) -> str:
        return self._impl.provider

    @property
    def representation_version(self) -> int:
        return self._impl.representation_version

    @property
    def model_revision(self) -> Optional[str]:
        return getattr(self._impl, "model_revision", None)

    @property
    def device(self) -> str:
        return getattr(self._impl, "device", "cpu")

    @property
    def batch_size(self) -> int:
        return getattr(self._impl, "batch_size", 32)

    def is_available(self) -> bool:
        return self._impl.is_available()

    def get_model_metadata(self) -> Dict[str, Any]:
        return self._impl.get_metadata()

    def embed_text(self, text: str) -> List[float]:
        return self._impl.embed_text(text)

    def embed_texts(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        return self._impl.embed_texts(texts, batch_size=batch_size)

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        return self._impl.cosine_similarity(vec_a, vec_b)

    def get_interim_baseline_service(self) -> InterimHashingEmbeddingService:
        """Returns the preserved interim hashing service for comparative evaluation."""
        return self._interim_baseline

    def reembed_chunks(
        self,
        db: Session,
        batch_size: int = 32,
        force_all: bool = False,
        max_chunks: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Safe, idempotent, resumable migration workflow to regenerate embeddings
        for existing DocumentChunk records from canonical stored text.
        Tracks progress, model ID, representation version, and errors without false success.
        """
        from backend.app.models.document import DocumentChunk

        query = db.query(DocumentChunk)
        if not force_all:
            # Select chunks that lack an embedding or have an older representation version
            query = query.filter(
                (DocumentChunk.embedding.is_(None)) |
                (DocumentChunk.embedding_version != self.representation_version) |
                (DocumentChunk.embedding_model != self.model_name)
            )

        query = query.order_by(DocumentChunk.id.asc())
        if max_chunks:
            query = query.limit(max_chunks)

        eligible_chunks = query.all()
        total_eligible = len(eligible_chunks)

        if total_eligible == 0:
            return {
                "status": "up_to_date",
                "total_eligible": 0,
                "processed_count": 0,
                "updated_count": 0,
                "failed_count": 0,
                "failed_ids": [],
                "target_model": self.model_name,
                "target_version": self.representation_version
            }

        processed_count = 0
        updated_count = 0
        failed_count = 0
        failed_ids: List[str] = []

        # Process in batches
        for i in range(0, total_eligible, batch_size):
            batch = eligible_chunks[i:i + batch_size]
            texts = [c.content for c in batch]
            try:
                vectors = self.embed_texts(texts, batch_size=batch_size)
                for chunk_obj, vec in zip(batch, vectors):
                    chunk_obj.embedding = json.dumps(vec)
                    chunk_obj.embedding_model = self.model_name
                    chunk_obj.embedding_version = self.representation_version
                    chunk_obj.indexed_in_es = False  # Marks Elasticsearch index as requiring synchronization
                    updated_count += 1
                db.commit()
                processed_count += len(batch)
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to re-embed chunk batch [{i}:{i+len(batch)}]: {e}")
                failed_count += len(batch)
                failed_ids.extend([c.id for c in batch])

        status = "completed" if failed_count == 0 else ("partial_failure" if updated_count > 0 else "failed")

        return {
            "status": status,
            "total_eligible": total_eligible,
            "processed_count": processed_count,
            "updated_count": updated_count,
            "failed_count": failed_count,
            "failed_ids": failed_ids,
            "target_model": self.model_name,
            "target_version": self.representation_version
        }


embedding_service = EmbeddingService(dimension=384)
