# DataNexus — Local Development & Setup Guide

This guide provides exact, tested step-by-step instructions for running, testing, and developing DataNexus locally on Windows, macOS, or Linux.

---

## 1. Prerequisites

- **Python**: 3.11, 3.12, or 3.13 (64-bit)
- **Node.js**: v18.0.0 or higher
- **npm**: v9.0.0 or higher
- **Git**: 2.30+

> **Note on Docker**: Docker is **not** required for local development. DataNexus is architected to run out of the box using native Python virtual environments and an embedded SQLite database with zero external service dependencies.

---

## 2. Quickstart (Under 3 Minutes)

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/harshitxmishra/DataNexus.git
cd DataNexus
cp .env.example .env
```

### Step 2: Set Up Backend Virtual Environment
**Windows PowerShell**:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

**macOS / Linux**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Step 3: Set Up Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### Step 4: Seed Demonstration Data
Run the database seeder to generate 6 sample PDF invoices and initial dimensional star-schema facts:
```bash
python scripts/seed_database.py
```

### Step 5: Start Development Servers

**Terminal 1 — Backend (FastAPI)**:
```bash
# From project root:
.venv\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8008 --reload
# (On macOS/Linux: uvicorn backend.app.main:app --host 127.0.0.1 --port 8008 --reload)
```
*API Swagger Documentation is available at: `http://127.0.0.1:8008/docs`*

**Terminal 2 — Frontend (Vite + React)**:
```bash
cd frontend
npm run dev
```
*Frontend Application opens at: `http://localhost:5173` (or `http://localhost:5174` if port 5173 is in use).*

---

## 3. Automated Testing & Verification

### Running Backend Unit & Regression Tests
DataNexus uses `pytest` with full async test client support:
```bash
# Run all tests with verbose output:
python -m pytest backend/tests -v
```
Expected output:
```
backend/tests/test_api_endpoints.py::test_health_endpoints PASSED
backend/tests/test_api_endpoints.py::test_documents_lifecycle PASSED
backend/tests/test_api_endpoints.py::test_search_and_qa_api PASSED
backend/tests/test_api_endpoints.py::test_data_platform_and_analytics_api PASSED
backend/tests/test_api_endpoints.py::test_processing_performance_regression PASSED
backend/tests/test_api_endpoints.py::test_duplicate_candidates_api PASSED
backend/tests/test_extraction.py::test_chunking_offsets PASSED
backend/tests/test_extraction.py::test_extract_invoice_fields PASSED
backend/tests/test_search_and_qa.py::test_embeddings_generation PASSED
backend/tests/test_search_and_qa.py::test_search_modes PASSED
backend/tests/test_search_and_qa.py::test_qa_service_with_citations_and_insufficiency PASSED
backend/tests/test_storage.py::test_sanitize_filename PASSED
backend/tests/test_storage.py::test_calculate_file_hash PASSED
backend/tests/test_storage.py::test_save_upload_pdf PASSED
====================== 14 passed in ~36s =======================
```

### Running Frontend Production Build
```bash
cd frontend
npm run build
```
Ensures TypeScript strict mode checks pass and generates the optimized production bundle in `frontend/dist/`.

### Running the End-to-End Smoke Test
Verify active service endpoints while the backend server is running:
```bash
python scripts/smoke_test.py
```

---

## 4. Optional Service Configurations

### 4.1 Connecting to Elasticsearch
1. Start your local or cloud Elasticsearch instance:
   ```bash
   docker run -p 9200:9200 -e "discovery.type=single-node" -e "xpack.security.enabled=false" docker.elastic.co/elasticsearch/elasticsearch:8.11.0
   ```
2. In `.env`, set:
   ```env
   ELASTICSEARCH_URL=http://localhost:9200
   ELASTICSEARCH_INDEX=datanexus_documents
   ```
3. When connected, DataNexus automatically utilizes Elasticsearch for BM25 and KNN vector search. If offline, the platform falls back gracefully to in-process cosine similarity and token matching without interruption.

### 4.2 Connecting to PostgreSQL
1. Start PostgreSQL:
   ```bash
   docker run -p 5432:5432 -e POSTGRES_DB=datanexus -e POSTGRES_PASSWORD=postgres -d postgres:16
   ```
2. Update `.env`:
   ```env
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/datanexus
   ```
3. Run the database seed script to initialize tables, curated views, and seed data.

### 4.3 Enabling Gemini Retrieval-Augmented Generation (RAG)
1. Obtain an API key from Google AI Studio.
2. Update `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini-1.5-flash
   ```

---

## 5. Troubleshooting Common Issues

### Issue 1: Port 8000 or 8008 Already in Use
- **Cause**: Another local process is bound to the target port.
- **Solution**: Pass an alternative port to Uvicorn (e.g. `--port 8009`) and update `target` in `frontend/vite.config.ts`.

### Issue 2: Python ModuleNotFoundError When Running Pytest
- **Cause**: Running `pytest` instead of `python -m pytest` might omit the current working directory from `sys.path`.
- **Solution**: Always invoke as `.venv\Scripts\python -m pytest backend/tests -v`.

### Issue 3: SQLite Database Locked
- **Cause**: Multiple write transactions concurrent with external SQLite database viewers.
- **Solution**: Close external database GUI tools (e.g., DB Browser for SQLite) when running write-heavy batch ETL scripts.
