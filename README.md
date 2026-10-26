# DataNexus Platform

> **"From unstructured documents to trusted, traceable intelligence."**

**DataNexus** is an enterprise-grade document intelligence, semantic retrieval, data engineering, and business intelligence platform built from scratch. It connects document ingestion, layout extraction, dense vector search, idempotent dimensional ETL, data quality governance, and executive analytics in one cohesive system.

Its defining capability is **end-to-end traceability**: inspecting a business insight or analytical spend metric on a dashboard and tracing it through the dimensional transformation pipeline to the extracted field, character offsets, supporting page text, and original binary document.

---

## 1. Key Capabilities

- **Document Intelligence & Ingestion**:
  - Safe file storage identified by SHA-256 hashes with directory traversal prevention.
  - Native PDF layout extraction (`pypdf`) and pluggable OCR architecture.
  - Automatic duplicate detection and versioning.
  - Page-aware text chunking with start/end character offsets.
  - Structured extraction for invoices: Invoice Number, Vendor, Dates, Currency, Subtotal, Tax, Total, Payment Status, and Line Items with extraction confidence metrics.

- **Semantic Retrieval & RAG Question Answering**:
  - 384-dimensional unit-normalized dense embeddings with cosine similarity.
  - Elasticsearch integration for BM25, KNN dense vectors, and Reciprocal Rank Fusion (RRF) hybrid search.
  - Resilient embedded search engine fallback when Elasticsearch is offline.
  - Traceable Document Question Answering (RAG) with verified page citations, evidence snippets, and honest insufficiency detection.

- **Data Platform & Dimensional Modeling (ETL/ELT)**:
  - Idempotent dimensional star-schema transformations (`dim_vendor`, `dim_date`, `fact_invoice`, `fact_invoice_line`, `fact_document_processing`, `fact_data_quality`, `fact_pipeline_run`).
  - Batch tracking with execution latency, rows read, inserted, updated, and rejected.
  - Automated deterministic Data Quality evaluation engine (8 core rules).
  - Tabular CSV dataset ingestion with schema validation and drift reporting.
  - Multi-hop Lineage Graph connecting raw files to downstream BI metrics.

- **Business Intelligence & Power BI**:
  - Curated PostgreSQL / SQLite analytical views (`v_invoice_spend_by_vendor`, `v_daily_ingestion`, `v_processing_performance`, `v_overdue_invoices`, `v_data_quality_scorecard`, `v_pipeline_freshness`).
  - Native Power BI Desktop connection guide with DAX measure specifications.
  - One-click CSV analytical export.

- **Distinctive Product Design**:
  - Purpose-built analytical workspace inspired by Linear, Stripe Dashboard, Metabase, and Vercel.
  - High-contrast, editorial layout with precision telemetry badges and interactive investigation panes.

---

## 2. Technology Stack

- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons, Recharts.
- **Backend**: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, ReportLab, PyPDF, Scikit-Learn, NumPy, Pytest.
- **Data & Storage**: PostgreSQL / SQLite dual-mode, Content-addressable storage, Elasticsearch (optional at runtime with automatic fallback).

---

## 3. Quickstart Guide (Local Windows / Cross-Platform)

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### Step 1: Environment & Virtual Environment
```powershell
# Clone or navigate to the repository
cd c:\Users\SujeetMishra\Desktop\Data_Nexus\DataNexus

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -r backend/requirements.txt
```

### Step 2: Seed Demonstration Database
DataNexus includes a synthetic seed generator that creates 6 realistic vector PDF invoices and populates the dimensional star schema, quality rules, and lineage catalog:
```powershell
python -m backend.app.seed
```

### Step 3: Run Backend Tests
```powershell
python -m pytest backend/tests -v
```

### Step 4: Start Backend API Server
```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8008 --reload
```
API Documentation will be live at: **http://127.0.0.1:8008/docs**

### Step 5: Start Frontend Dev Server
In a separate terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open your browser at: **http://localhost:5174** (or displayed port).

---

## 4. API Reference Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health/readiness` | Deep readiness probe checking DB, Elasticsearch, Embeddings, Queue, and LLM |
| `POST` | `/api/documents/upload` | Upload & validate PDF/CSV/image, calculate SHA-256, execute processing pipeline |
| `GET` | `/api/documents` | List documents with status, type, and search filters |
| `GET` | `/api/documents/{id}` | Complete document details with extracted fields, page text, chunks, and line items |
| `POST` | `/api/documents/{id}/reprocess` | Idempotently reprocess extraction, embeddings, and ETL facts |
| `DELETE` | `/api/documents/{id}` | Safely delete document and cascade to storage, chunks, and facts |
| `POST` | `/api/search/query` | Execute Lexical (BM25), Semantic (Vector), or Hybrid (RRF) search |
| `POST` | `/api/search/qa` | Retrieval-augmented Question Answering with citations and insufficiency detection |
| `POST` | `/api/data-platform/pipeline/run` | Manually trigger incremental dimensional ETL pipeline |
| `GET` | `/api/data-platform/quality/scorecard`| Summary scorecard of rule pass/fail rates |
| `GET` | `/api/lineage/document/{id}` | Multi-hop directed lineage graph for a document |
| `GET` | `/api/analytics/overview` | Platform-wide operational and spend KPIs |
| `GET` | `/api/analytics/vendor-spend` | Invoiced spend aggregated by vendor and currency |
| `GET` | `/api/analytics/overdue-invoices` | Overdue liability exposure and days overdue |
| `GET` | `/api/data-platform/export/invoices` | Stream curated analytical invoice dataset as CSV |

---

## 5. Verified Test Suite Results

```text
backend/tests/test_api_endpoints.py::test_health_endpoints PASSED
backend/tests/test_api_endpoints.py::test_documents_lifecycle PASSED
backend/tests/test_api_endpoints.py::test_search_and_qa_api PASSED
backend/tests/test_api_endpoints.py::test_data_platform_and_analytics_api PASSED
backend/tests/test_extraction.py::test_chunking_offsets PASSED
backend/tests/test_extraction.py::test_extract_invoice_fields PASSED
backend/tests/test_search_and_qa.py::test_embeddings_generation PASSED
backend/tests/test_search_and_qa.py::test_search_modes PASSED
backend/tests/test_search_and_qa.py::test_qa_service_with_citations_and_insufficiency PASSED
backend/tests/test_storage.py::test_sanitize_filename PASSED
backend/tests/test_storage.py::test_calculate_file_hash PASSED
backend/tests/test_storage.py::test_save_upload_pdf PASSED

====================== 12 passed in 37.21s =======================
```
