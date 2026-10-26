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
| **Embedding Generation** | In-process TF-IDF character n-gram hasher with $L_2$ normalization (384-d) | :warning: Interim Representation | Not a pretrained neural Transformer model. Must transition to genuine pretrained embeddings in Phase 3. |
| **Question Answering (RAG)** | Evidence-gated RAG with citation validation & insufficiency detection | :white_check_mark: Operational (Local) | Currently uses rule-based evidence synthesis when API keys are unconfigured. Groq integration needed in Phase 4. |
| **Dimensional Modeling & ETL** | Idempotent dimensional star schema (`dim_vendor`, `dim_date`, `fact_invoice`...) | :white_check_mark: Operational | Verified with 6 seeded invoices and incremental upsert logic. |
| **Data Quality Rules** | Deterministic rules engine (8 rules) auditing completeness, balance, dates | :white_check_mark: Operational | Verified with pass/warn/fail scorecard reporting. |
| **Lineage Graph (DAG)** | Multi-hop lineage recording: file -> document -> field -> fact -> view -> metric | :white_check_mark: Operational | Interactive lineage graph API verified. |
| **Curated SQL Views** | 7 pre-aggregated analytical views in `views.py` | :warning: Dialect-Dependent | Contains SQLite string functions (`substr`); requires ANSI / PostgreSQL compatibility adjustments (Phase 1). |
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
   - Checkpoint commit: `feat(database): implement PostgreSQL support and Alembic migrations`.
