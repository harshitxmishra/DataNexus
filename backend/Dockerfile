# ============================================================
# DataNexus v2.0.0 Backend — Multi-Stage Production Dockerfile
# Python 3.13-slim, Non-Root User, Pre-cached Neural & ONNX Models
# ============================================================

# Stage 1: Dependency builder & model pre-caching
FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /build/requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r /build/requirements.txt

# Pre-cache sentence-transformers and FlashRank models into /models
ENV HF_HOME=/models/hf \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence_transformers \
    FLASHRANK_CACHE_DIR=/models/flashrank

RUN python -c "\
import os;\
os.environ['HF_HOME'] = '/models/hf';\
os.environ['SENTENCE_TRANSFORMERS_HOME'] = '/models/sentence_transformers';\
from sentence_transformers import SentenceTransformer;\
m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2');\
print('Pre-cached MiniLM model successfully');\
from flashrank import Ranker;\
r = Ranker(model_name='ms-marco-MiniLM-L-12-v2', cache_dir='/models/flashrank');\
print('Pre-cached FlashRank ONNX model successfully');\
"

# Stage 2: Minimal runtime image
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/models/hf \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence_transformers \
    FLASHRANK_CACHE_DIR=/models/flashrank \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/app"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages and pre-cached models from builder
COPY --from=builder /install /usr/local
COPY --from=builder /models /models

# Create non-root application user
RUN groupadd -g 10001 datanexus && \
    useradd -u 10001 -g datanexus -s /bin/bash -m datanexus

# Copy application codebase
COPY backend/ /app/backend/
COPY scripts/ /app/scripts/
COPY alembic.ini /app/alembic.ini

# Create storage and models directories with non-root ownership
RUN mkdir -p /app/data/storage /app/data/exports /app/data/staging && \
    chown -R datanexus:datanexus /app /models && \
    chmod -R 775 /app/data && \
    chmod +x /app/scripts/docker-entrypoint.sh 2>/dev/null || true

USER datanexus

EXPOSE 8008

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8008/api/health/liveness || exit 1

ENTRYPOINT ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8008"]
