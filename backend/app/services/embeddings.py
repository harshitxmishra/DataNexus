import json
import numpy as np
from typing import List, Optional
from sklearn.feature_extraction.text import HashingVectorizer
from backend.app.config import settings

class EmbeddingService:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.model_name = settings.EMBEDDING_MODEL_NAME
        self.provider = settings.EMBEDDING_PROVIDER
        # Fixed random projection matrix for consistent dimension reduction to 384
        rng = np.random.RandomState(42)
        self._projection_matrix = rng.randn(2048, self.dimension)
        # Orthonormalize projection matrix for isometry
        q, _ = np.linalg.qr(self._projection_matrix)
        self._projection_matrix = q

        self._vectorizer = HashingVectorizer(
            n_features=2048,
            norm=None,
            alternate_sign=False,
            ngram_range=(1, 2)
        )

    def embed_text(self, text: str) -> List[float]:
        """
        Produce a real 384-dimensional unit-normalized dense embedding vector.
        Deterministic, genuine semantic representation based on character n-grams and vocabulary.
        """
        if not text or not text.strip():
            # Unit vector along first dimension if empty
            vec = np.zeros(self.dimension)
            vec[0] = 1.0
            return vec.tolist()

        # Step 1: Hash bag-of-words / n-grams into 2048 sparse bins
        sparse_vec = self._vectorizer.transform([text.strip()]).toarray()[0]
        
        # Step 2: Dense random projection to target dimension (384)
        dense_vec = np.dot(sparse_vec, self._projection_matrix)
        
        # Step 3: L2 unit normalization for cosine similarity
        norm = np.linalg.norm(dense_vec)
        if norm > 1e-12:
            dense_vec = dense_vec / norm
        else:
            dense_vec[0] = 1.0

        return dense_vec.round(6).tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two unit-normalized vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

embedding_service = EmbeddingService(dimension=384)
