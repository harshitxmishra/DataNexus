# DataNexus — Implementation Baseline & Gap Analysis (Phase 0)

**Date**: 2026-10-26  
**Auditor**: Principal Software Architect & Lead Engineer  
**Status**: Baseline Established & Verified

---

## 1. Executive Summary

This document establishes the verified, factual starting point for the long-term evolution of DataNexus. It documents the current capabilities, runtime configuration, database state, search architecture, data engineering pipelines, test coverage, and concrete technical gaps prior to executing Phase 1 (PostgreSQL Migration).

---

## 2. Runtime & Environment Audit

- **Operating System**: Windows 11 x64 (Native)
- **Python Runtime**: Python 3.13.7 (`.venv\Scripts\python.exe`)
- **Node.js / npm**: Node.js v18+ / npm v9+
- **Active Backend Server**: FastAPI running on `http://127.0.0.1:8008` (Process 5632 / Uvicorn)
- **Active Frontend Dev Server**: Vite running on `http://localhost:5174` with proxy to port 8008
- **Git Baseline**: Clean working tree on `main` tracking `origin/main` at commit `bff1dfe`
- **External Services**:
  - Docker Desktop daemon is currently stopped / unavailable.
  - Native PostgreSQL service is not installed on the host system.
  - Elasticsearch cluster on port 9200 is not running; local fallback is active.

---

## 3. Subsystem Audit & Capability Matrix

| Capability / Subsystem | Current Implementation | Status | Gaps & Next Actions |
|---|---|---|---|
| **Primary Database** | SQLite (`datanexus.db`) initialized via `Base.metadata.create_all` | :white_check_mark: Operational (Local) | Needs PostgreSQL driver, clean URL configuration, dialect-aware SQL views, and Alembic migrations (Phase 1). |
| **Migrations** | None (direct DDL execution via SQLAlchemy metadata) | :warning: Technical Debt | Alembic is installed in `.venv` (v1.20.1) but `alembic.ini` and migration scripts are not yet established (Phase 1). |
| **File Storage** | Content-addressable storage (`data/storage/`) using SHA-256 hashes | :white_check_mark: Operational | File path sanitization and duplicate detection verified. |
| **PDF Text Extraction** | Native `pypdf` extraction with character offsets & regex parsing | :white_check_mark: Operational | High precision on vector PDFs. OCR fallback is interface-only. |
| **Queue / Background Jobs** | Database-backed durable queue (`queue_jobs` table) in `queue.py` | :white_check_mark: Operational | Idempotent lifecycle execution verified. Redis is optional future enhancement. |
| **Search Engine** | Dual-provider router: `ElasticsearchProvider` + `LocalSearchProvider` | :white_check_mark: Operational (Fallback) | Elasticsearch is offline; local cosine similarity & token matching works cleanly. Real ES validation needed in Phase 2. |
| **Embedding Generation** | Pretrained neural Transformer (`sentence-transformers/all-MiniLM-L6-v2`, 384-d) | :white_check_mark: Operational (Pretrained MiniLM) | Real pretrained weights loaded in CPU inference; representation versioning (v2) and idempotent re-embedding verified (Phase 3). |
| **Question Answering (RAG)** | Fast GroqCloud LLM inference with negative gating, verifiable citations, multi-model fallback, and local extractive fallback | :white_check_mark: Operational (GroqCloud RAG) | Fully operational via `GroqRAGService` (`qwen/qwen3.8-27b`), negative question refusal, inline citation mapping, and multi-model fallback (Phase 4). |
| **Dimensional Modeling & ETL** | Idempotent dimensional star schema (`dim_vendor`, `dim_date`, `fact_invoice`...) | :white_check_mark: Operational | Verified with 6 seeded invoices and incremental upsert logic. |
| **Data Quality Rules** | Deterministic governance engine (11 rules) auditing completeness, balance, dates, line items, and terms | :white_check_mark: Operational (11-Rule Governance) | Comprehensive 11-rule audit suite with on-demand evaluation, by-rule and by-category scorecard breakdowns (Phase 5). |
| **Lineage Graph (DAG)** | Multi-hop directed lineage DAG (6 hops: file -> document -> field -> fact -> view -> metric) | :white_check_mark: Operational (6-Hop DAG) | Multi-hop BFS traversal, directional filtering (upstream/downstream), and rich node metadata resolution (Phase 5). |
| **Curated SQL Views** | 7 pre-aggregated analytical views in `views.py` | :white_check_mark: Operational (Dual Dialect & API) | 7 views verified across PostgreSQL and SQLite; queryable dynamically via `/api/analytics/views` and Power BI DirectQuery (Phase 5). |
| **Frontend Workspaces** | 5 React 18 workspaces (Overview, Documents, Detail, Search, BI) | :white_check_mark: Operational | High-density dark-slate design system with live telemetry verified. |

---

## 4. Test & Verification Baseline

The backend automated test suite (`python -m pytest backend/tests -v`) passes 14/14 tests:
- `test_health_endpoints`: Liveness & deep readiness telemetry.
- `test_documents_lifecycle`: Ingestion, details, download, and reprocessing.
- `test_search_and_qa_api`: Hybrid search and RAG question answering.
- `test_data_platform_and_analytics_api`: Pipeline execution, quality scorecard, overview KPIs.
- `test_processing_performance_regression`: Processing performance aggregation.
- `test_duplicate_candidates_api`: Duplicate document detection.
- `test_chunking_offsets`: Character bounds and window overlaps.
- `test_extract_invoice_fields`: Field regex patterns and line items.
- `test_embeddings_generation`: 384-d vector dimension and unit norm.
- `test_search_modes`: Lexical, semantic, and hybrid retrieval modes.
- `test_qa_service_with_citations_and_insufficiency`: Evidence gating and citations.
- `test_storage`: Sanitization, hashing, and upload persistence.

Frontend build (`npm run build` in `frontend/`) compiles with 0 errors in 4.19s.  
End-to-end smoke test (`python scripts/smoke_test.py`) reports `[PASS] All critical smoke tests verified successfully`.

---

## 5. Phase 1 Implementation Plan: PostgreSQL Migration

### Objective
Migrate DataNexus from SQLite-only assumptions to first-class PostgreSQL support while retaining clean zero-dependency SQLite fallback for lightweight development.

### Scope of Work for Phase 1
1. **PostgreSQL Driver**: Add `psycopg2-binary` (or `psycopg`) to `backend/requirements.txt` and install in `.venv`.
2. **Database Engine & Connection Pooling**:
   - Refactor `backend/app/database.py` to support PostgreSQL connection pooling (`pool_size`, `max_overflow`, `pool_pre_ping`).
   - Cleanly isolate SQLite pragmas so they only execute when connecting to SQLite.
3. **Dialect-Aware Analytical Views**:
   - Refactor `backend/app/models/views.py` to create PostgreSQL-compatible views (`CREATE OR REPLACE VIEW`, ANSI `DATE(created_at)`, `NUMERIC` casting for averages).
4. **Alembic Database Migrations**:
   - Initialize Alembic environment in `backend/alembic/`.
   - Configure `alembic.ini` and `env.py` pointing to `Base.metadata` and dynamic `DATABASE_URL`.
   - Generate initial migration revision covering all operational tables, staging tables, and dimensional star-schema models.
5. **Database Migration Utility**:
   - Implement `scripts/migrate_sqlite_to_postgres.py` to safely copy existing records from SQLite to PostgreSQL without data loss.
6. **Automated Testing**:
   - Add PostgreSQL dialect schema generation and query validation tests in `backend/tests/test_database_postgres.py`.
   - Ensure all 14 existing tests continue to pass without regression.
7. **Commit & Verification Gate**:
   - Checkpoint commit: `19938e1` (`feat(database): implement PostgreSQL support, Alembic migrations, and SQLite migration utility`). Verified in `docs/PHASE_1_VERIFICATION.md`.

---

## 6. Phase 2 Implementation: Elasticsearch Integration

### Objective
Implement a production-grade Elasticsearch provider supporting BM25 full-text retrieval, 384-dimensional dense vector k-NN search, native Reciprocal Rank Fusion (RRF), idempotent upsert, bulk indexing, deletion propagation, outbox-driven index reconciliation, and frontend status observability while strictly preserving PostgreSQL as the single source of truth.

### Execution Summary
- **Elasticsearch Provider**: Implemented in `backend/app/services/search.py` with versioned index mappings, multi-match BM25 boosting (`content^2.0`, `filename^1.0`), 384-d cosine vector kNN, and RRF rank fusion DSL.
- **Outbox Consistency Strategy**: Added tracking via `DocumentChunk.indexed_in_es`. Offline chunks remain flagged for reconciliation rather than silently marked as indexed.
- **Reconciliation & Reindex API**: `POST /api/search/reconcile` detects missing, orphaned, and stale records; `POST /api/search/reindex` bulk syncs database chunks to Elasticsearch.
- **Deletion Propagation**: `DELETE /api/documents/{id}` issues `delete_by_query` to clean up associated chunks from Elasticsearch.
- **Resilient Fallback**: If Elasticsearch is offline or times out, DataNexus falls back to the in-process `LocalSearchProvider` without failing user operations.
- **Frontend Truthful Telemetry**: `SearchPage.tsx` displays active provider status (Elasticsearch vs. Local Fallback) with live indexed chunk metrics.
- **Automated Tests**: 13 unit/contract tests added in `backend/tests/test_elasticsearch_provider.py`; all 38 backend tests passed (1 live test skipped cleanly). Verified in `docs/PHASE_2_VERIFICATION.md`.

---

## 7. Phase 3 Implementation: Genuine Pretrained Semantic Embeddings

### Objective
Replace the interim lexical hashing and projection vector representation with a genuine pretrained neural Transformer model (`sentence-transformers/all-MiniLM-L6-v2`), establish schema and index representation versioning, implement an idempotent re-embedding pipeline, decouple lexical retrieval for operational resilience, and execute a formal retrieval evaluation benchmark.

### Execution Summary
- **Model Integration**: Integrated `PretrainedNeuralEmbeddingService` in `backend/app/services/embeddings.py` using `sentence-transformers/all-MiniLM-L6-v2` (revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`). Verified 384-d output, strictly finite values, and unit $L_2$-normalization.
- **Representation Versioning**: Added `embedding_model` and `embedding_version` (v1 legacy vs. v2 neural) to `DocumentChunk` via Alembic migration `fd604e91c2f1` and updated Elasticsearch index mappings.
- **Idempotent Re-Embedding Pipeline**: Implemented `POST /api/search/reembed` supporting batched execution, progress telemetry, and automatic re-indexing.
- **Decoupled Search Resilience**: Decoupled BM25 lexical search from vector inference so lexical search remains 100% operational during neural model cold starts or outages.
- **Retrieval Benchmark**: Developed 10-query benchmark (`backend/app/evaluation/retrieval_eval.py`). MiniLM v2 achieved Recall@3 = 1.000 and MRR = 0.944 (vs 0.753 for interim hashing).
- **Automated Tests**: 13 tests added in `backend/tests/test_neural_embeddings.py`; full suite passes 54/55 tests (1 live ES check cleanly skipped). Full verification documented in `docs/PHASE_3_VERIFICATION.md`.

---

## 8. Phase 4 Implementation: GroqCloud LLM Integration & Production-Minded RAG

### Objective
Integrate fast GroqCloud LLM inference into the Question Answering / RAG pipeline, enforcing strict factual grounding, verifiable source citations, negative evidence gating (`evidence_status: "insufficient"`), multi-model fallback, resilient local extractive synthesis, and comprehensive regression test suites.

### Execution Summary
- **Groq Cloud Service**: Implemented `GroqRAGService` in `backend/app/services/groq_service.py` with thread-safe lazy client initialization, candidate model fallback loop, latency tracking, and token usage accounting.
- **Model Selection & Availability**: Evaluated active Groq models; selected `qwen/qwen3.8-27b` as primary for sub-2.5s generation without reasoning token exhaustion, with `llama-3.3-70b-versatile,llama-3.1-8b-instant,openai/gpt-oss-120b,openai/gpt-oss-20b` configured as resilient fallbacks.
- **Strict Factual Grounding**: Engineered system prompt enforcing strict context-only constraints, `[Source N]` tags, and exact `INSUFFICIENT_EVIDENCE:` directive on missing facts.
- **Citation Mapping**: Parsed `[Source N]` tags into structured `Citation` domain objects linking to canonical document IDs, filenames, page numbers, and snippet excerpts.
- **Zero-Failure Fallback**: Preserved deterministic extractive synthesis fallback (`extractive_evidence_synthesis`) if Groq API keys are absent, revoked, or rate-limited.
- **Operational Readiness**: Enriched `/api/health/readiness` with `llm_provider` status (`ready` vs `fallback_extractive`), active model name, and configuration state.
- **Automated Tests**: Added 8 unit and integration tests in `backend/tests/test_groq_rag.py`. Total test suite passes 62/63 tests (1 live ES test skipped). Full verification documented in `docs/PHASE_4_VERIFICATION.md`.

---

## 9. Phase 5 Implementation: Data Quality, Multi-Hop Lineage & Power BI Semantic Models

### Objective
Establish an enterprise-grade data governance and business intelligence foundation by expanding the data quality rules engine to 11 deterministic rules with on-demand evaluation and detailed category/rule scorecards, implementing an interactive 6-hop directed lineage DAG with BFS traversal and directional filtering, verifying 7 curated analytical SQL views, and publishing a formal Power BI semantic model specification.

### Execution Summary
- **11-Rule Data Quality Engine**: Added `LINE_ITEMS_SUM_CONSISTENCY`, `INVOICE_DATE_SANITY`, and `PAYMENT_TERMS_SANITY` to `backend/app/services/quality.py`. Implemented `evaluate_all_documents(db)` and `get_detailed_scorecard(db)` delivering by-rule and by-category compliance distributions.
- **On-Demand Quality Evaluation API**: Added `POST /api/data-platform/quality/evaluate` (all or single document) and enriched `GET /api/data-platform/quality/scorecard`.
- **Interactive Multi-Hop Lineage Graph**: Upgraded `backend/app/services/lineage.py` to use Breadth-First Search (BFS) graph traversal with directional filtering (`document`, `upstream`, `downstream`, `all`) and rich node metadata resolution (file, document, extracted_field, fact_invoice, view, metric). Added `GET /api/lineage/summary`.
- **Curated Analytical SQL Views & API**: Verified all 7 views (`v_daily_ingestion`, `v_processing_performance`, `v_invoice_spend_by_vendor`, `v_overdue_invoices`, `v_data_quality_scorecard`, `v_pipeline_freshness`, `v_indexing_coverage`). Added `GET /api/analytics/views` and safe whitelisted dynamic query endpoint `GET /api/analytics/views/{view_name}`.
- **Power BI Semantic Model Specification**: Implemented `GET /api/analytics/powerbi/semantic-model` exposing complete Kimball star schema, relationship cardinalities (1:*, inactive due date), 8 production DAX measures with format strings, and DirectQuery connection parameters.
- **Frontend Workspaces**: Upgraded `DataPlatformPage.tsx` with rule-by-rule scorecard progress bars, on-demand evaluation trigger, category summary badges, directional lineage filters, and interactive node metadata inspector. Upgraded `AnalyticsPage.tsx` with Power BI semantic model explorer, star-schema relationships card, copyable DAX measure library, and live SQL view table previewer.
- **Automated Tests**: 17 unit and integration tests added in `backend/tests/test_data_platform_phase5.py`. Total test suite passes 79/80 tests (1 live ES test skipped). Full verification documented in `docs/PHASE_5_VERIFICATION.md`.

---

## 10. Phase 6 Implementation: Production Deployment, Real-Time Streaming & Power BI Automation

### Objective
Complete the production readiness of DataNexus by implementing an asynchronous Server-Sent Events (SSE) streaming engine for sub-second pipeline progression, an automated Power BI M-queries generator and downloadable script exporter, and multi-container Docker Compose orchestration uniting PostgreSQL 16, Elasticsearch 8.11, FastAPI backend, and Nginx/React frontend.

### Execution Summary
- **Real-Time Streaming Engine**: Implemented `PipelineEventBroadcaster` in `backend/app/services/streaming.py` with in-memory async pub/sub, channel isolation (`doc:{id}` vs `global`), keepalive pings, and thread-safe `emit_sync()` hooks inside `ProcessingQueueService`.
- **SSE Endpoints**: Added `GET /api/documents/{id}/events/stream` (historical snapshot + live events) and `GET /api/documents/events/stream` (global feed).
- **Power BI M-Queries & Script Generator**: Implemented `GET /api/analytics/powerbi/m-queries` generating dialect-aware Power Query (M) code for all 6 star-schema entities and 7 curated views, and `GET /api/analytics/powerbi/export-script` for downloadable `.pq` templates.
- **Production Containerization**: Created `Dockerfile.backend`, `Dockerfile.frontend`, `nginx.conf`, `docker-compose.yml`, and `scripts/docker-entrypoint.sh` with automated migrations, seeding, healthchecks, and reverse proxying with SSE buffering disabled.
- **Frontend Real-Time Telemetry**: Added live SSE badge, streaming stage progression banners, and one-click reprocess button in `DocumentDetailPage.tsx`; added interactive M-query code viewer and `.pq` script exporter in `AnalyticsPage.tsx`.
- **Automated Tests**: Added 9 dedicated tests in `backend/tests/test_phase6_production_readiness.py`. Total test suite passes 88/89 tests (1 live ES test skipped). Full verification documented in `docs/PHASE_6_VERIFICATION.md`.




