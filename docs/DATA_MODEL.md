# DataNexus — Data Models & Dimensional Schema

DataNexus organizes data into three distinct architectural tiers:
1. **Operational Layer**: Documents, stage events, raw text chunks, and extracted fields.
2. **Staging & Platform Layer**: Ingestion batches, data quality audits, CSV staging, and lineage edges.
3. **Dimensional Analytical Layer (Star Schema)**: Fact and dimension tables with curated SQL reporting views for Power BI.

---

## 1. Dimensional Star Schema (Analytical Tier)

```
                       +-------------------------+
                       |        dim_date         |
                       |-------------------------|
                       | date_key (PK, YYYYMMDD) |
                       | full_date               |
                       | year, quarter, month    |
                       +-------------------------+
                                    |
                                    | invoice_date_key / due_date_key
                                    v
+-------------------------+    +--------------------------------+    +-----------------------+
|       dim_vendor        |    |          fact_invoice          |    |   fact_invoice_line   |
|-------------------------|    |--------------------------------|    |-----------------------|
| vendor_key (PK, int)    |<---| invoice_key (PK, int)          |<---| line_key (PK, int)    |
| vendor_name             |    | document_id (FK, unique)       |    | invoice_key (FK)      |
| normalized_vendor_name  |    | vendor_key (FK)                |    | line_number           |
| category                |    | invoice_date_key (FK)          |    | description           |
| first_seen_date         |    | due_date_key (FK)              |    | quantity, unit_price  |
+-------------------------+    | currency (ISO-4217)            |    | amount                |
                               | subtotal, tax_amount, total    |    +-----------------------+
                               | payment_status, is_overdue     |
                               | days_overdue                   |
                               +--------------------------------+
```

### 1.1 Dimension Tables

#### `dim_vendor`
- **Grain**: One row per distinct business vendor.
- **Key**: `vendor_key` (Integer PK, autoincrement).
- **Columns**:
  - `vendor_name` (`VARCHAR(255)`): Official vendor display name.
  - `normalized_vendor_name` (`VARCHAR(255)`, indexed, unique): Lowercased, trimmed vendor identifier.
  - `category` (`VARCHAR(100)`): Vendor industry classification.
  - `country` (`VARCHAR(50)`): Two-letter or full country identifier.
  - `first_seen_date` (`VARCHAR(20)`): Date when vendor first appeared.

#### `dim_date`
- **Grain**: One row per calendar date.
- **Key**: `date_key` (Integer PK in `YYYYMMDD` format).
- **Columns**:
  - `full_date` (`DATE`): Date timestamp.
  - `year` (`INT`), `quarter` (`INT`), `month` (`INT`), `month_name` (`VARCHAR(20)`).
  - `week` (`INT`), `day_of_month` (`INT`), `day_name` (`VARCHAR(20)`).
  - `is_weekend` (`BOOLEAN`): True if Saturday or Sunday.

### 1.2 Fact Tables

#### `fact_invoice`
- **Grain**: One row per validated invoice business transaction.
- **Key**: `invoice_key` (Integer PK, autoincrement).
- **Foreign Keys**:
  - `document_id` (`VARCHAR(36)`, unique FK -> `documents.id`)
  - `vendor_key` (`INT` FK -> `dim_vendor.vendor_key`)
  - `invoice_date_key` (`INT` FK -> `dim_date.date_key`)
  - `due_date_key` (`INT` FK -> `dim_date.date_key`, nullable)
- **Measures & Status**:
  - `currency` (`VARCHAR(10)`): ISO currency code (e.g., `USD`, `EUR`, `GBP`).
  - `subtotal` (`DECIMAL(12, 2)`): Invoice subtotal before taxes.
  - `tax_amount` (`DECIMAL(12, 2)`): Extracted tax amount.
  - `total_amount` (`DECIMAL(12, 2)`): Final invoice total.
  - `payment_status` (`VARCHAR(50)`): `Paid`, `Pending`, or `Overdue`.
  - `is_overdue` (`BOOLEAN`): Computed dynamically based on due date.
  - `days_overdue` (`INT`): Elapsed days past the payment due date.
  - `extraction_confidence` (`FLOAT`): Confidence score $[0.0, 1.0]$.

#### `fact_invoice_line`
- **Grain**: One row per extracted invoice line item.
- **Key**: `line_key` (Integer PK, autoincrement).
- **Foreign Keys**:
  - `invoice_key` (`INT` FK -> `fact_invoice.invoice_key`)
  - `document_id` (`VARCHAR(36)`)
- **Measures**:
  - `line_number` (`INT`): 1-indexed line position.
  - `description` (`TEXT`): Line item description text.
  - `quantity` (`DECIMAL(10, 2)`): Extracted item quantity.
  - `unit_price` (`DECIMAL(12, 2)`): Price per unit.
  - `amount` (`DECIMAL(12, 2)`): Total line amount.

#### `fact_document_processing`
- **Grain**: One row per document processing lifecycle attempt.
- **Key**: `event_key` (Integer PK, autoincrement).
- **Columns**:
  - `document_id` (`VARCHAR(36)` FK -> `documents.id`, indexed).
  - `file_type` (`VARCHAR(100)`): Document MIME type.
  - `file_size_bytes` (`INT`): Size in bytes.
  - `page_count` (`INT`): Total pages parsed.
  - `processing_time_ms` (`INT`): Total pipeline latency.
  - `ocr_invoked` (`BOOLEAN`): True if fallback OCR was used.
  - `indexing_succeeded` (`BOOLEAN`): True if indexed in search engine.
  - `extraction_succeeded` (`BOOLEAN`): True if fields were extracted.
  - `final_status` (`VARCHAR(50)`): `completed`, `partially_completed`, `failed`.

#### `fact_data_quality`
- **Grain**: One row per evaluated quality rule.
- **Key**: `evaluation_key` (Integer PK, autoincrement).
- **Columns**:
  - `batch_id` (`VARCHAR(100)`): Evaluation run identifier.
  - `rule_name` (`VARCHAR(150)`): Specific rule evaluated.
  - `status` (`VARCHAR(50)`): `pass`, `warning`, `fail`.
  - `severity` (`VARCHAR(50)`): `error`, `warning`, `info`.
  - `entity_type` (`VARCHAR(100)`): `document`, `invoice`, `csv_dataset`.
  - `entity_id` (`VARCHAR(100)`): ID of evaluated record.

#### `fact_pipeline_run`
- **Grain**: One row per ETL pipeline execution.
- **Key**: `run_key` (Integer PK, autoincrement).
- **Columns**:
  - `pipeline_name` (`VARCHAR(100)`), `batch_id` (`VARCHAR(100)`).
  - `status` (`VARCHAR(50)`), `rows_processed` (`INT`), `rows_rejected` (`INT`).
  - `duration_ms` (`INT`).

---

## 2. Operational Tables

### `documents`
- Primary ingestion record containing `id` (UUID), `filename`, `file_type`, `file_size`, `file_hash` (SHA-256), `storage_path`, `status`, `page_count`, `character_count`, `extraction_confidence`, `version`, and timestamps.

### `document_stage_events`
- Records stage-level execution transitions (`text_extraction`, `field_extraction`, `chunking`, `embedding`, `indexing`, `analytics_transform`, `quality_validation`) with execution timestamps and durations.

### `extracted_fields`
- Stores individual extracted fields with character-level offsets (`start_char`, `end_char`), page number, raw text value, normalized value, extraction method, confidence, and validation status.

### `document_chunks`
- 500-character windows with 80-character overlaps. Contains `chunk_index`, `page_number`, `start_char`, `end_char`, `content`, and serialized `embedding` vectors (384 floats).

---

## 3. Data Platform & Lineage Tables

### `lineage_edges`
- Directed acyclic graph (DAG) tracking data provenance:
  - `source_type`: `file`, `document`, `extracted_field`, `fact_invoice`, `view`.
  - `source_id`: Identifier of the origin entity.
  - `target_type`: Target entity type.
  - `target_id`: Identifier of the destination entity.
  - `transformation_rule`: Description of transformation logic (e.g., `pipeline.invoice_dimensional_etl`).

### `data_quality_results`
- Persistent records of deterministic data quality audits:
  - Rules: `REQUIRED_INVOICE_FIELDS`, `VALID_INVOICE_DATE`, `NON_NEGATIVE_AMOUNTS`, `CURRENCY_CODE_VALIDITY`, `SUBTOTAL_TAX_BALANCE`, `DOCUMENT_NON_DUPLICATION`, `EXTRACTION_CONFIDENCE_THRESHOLD`, `INDEXING_COVERAGE`.

---

## 4. Curated Analytical SQL Views

DataNexus defines 7 pre-aggregated views for external BI consumption:

1. **`v_daily_ingestion`**: Daily document volumes, completed counts, failed counts, and average confidence.
2. **`v_processing_performance`**: Average, minimum, and maximum processing latencies grouped by document MIME type.
3. **`v_invoice_spend_by_vendor`**: Aggregate spend, invoice counts, and average confidence grouped by vendor and currency.
4. **`v_overdue_invoices`**: Overdue liabilities, invoice numbers, days overdue, and supplier names.
5. **`v_data_quality_scorecard`**: Pass/fail/warning rates by rule name and entity type.
6. **`v_pipeline_freshness`**: Most recent ETL batch timestamp, rows processed, and execution duration.
7. **`v_indexing_coverage`**: Total documents vs. indexed chunks and percentage coverage.
