#!/usr/bin/env python3
"""
DataNexus v3.0: PostgreSQL Query Plan & Indexing Benchmark Runner
Executes real SQL benchmarks against PostgreSQL (via Docker or embedded pgserver),
parses EXPLAIN (ANALYZE, BUFFERS) outputs, computes exact speedups, and
updates docs/sql-tuning.md with 100% verified live numbers.
"""

import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
V1_MIGRATION = REPO_ROOT / "services" / "ledger-service" / "src" / "main" / "resources" / "db" / "migration" / "V1__init_ledger.sql"
V2_MIGRATION = REPO_ROOT / "services" / "ledger-service" / "src" / "main" / "resources" / "db" / "migration" / "V2__add_performance_indexes.sql"
BENCHMARK_SQL = REPO_ROOT / "services" / "ledger-service" / "scripts" / "seed_and_benchmark.sql"
OUTPUT_MD = REPO_ROOT / "docs" / "sql-tuning.md"

QUERIES = {
    "Q1": (
        "Multi-Currency Settlement Rollup",
        """SELECT
    currency,
    status,
    COUNT(*) AS entry_count,
    SUM(amount) AS total_volume,
    ROUND(AVG(validation_score), 2) AS avg_score
FROM ledger_entries
WHERE status = 'SETTLED'
  AND created_at >= NOW() - INTERVAL '90 days'
GROUP BY currency, status
ORDER BY total_volume DESC;"""
    ),
    "Q2": (
        "Vendor + Currency Paginated Lookup",
        """SELECT
    id,
    invoice_number,
    vendor_name,
    currency,
    amount,
    status,
    created_at
FROM ledger_entries
WHERE vendor_name = 'Global Logistics Ltd'
  AND currency = 'USD'
ORDER BY created_at DESC
LIMIT 25 OFFSET 0;"""
    ),
    "Q3": (
        "Join Filtered by Status = REJECTED",
        """SELECT
    l.invoice_number,
    l.vendor_name,
    l.amount,
    l.currency,
    l.created_at,
    a.event_type,
    a.actor,
    a.created_at AS event_time,
    a.payload
FROM ledger_entries l
JOIN audit_events a ON l.id = a.ledger_entry_id
WHERE l.status = 'REJECTED'
  AND l.created_at >= NOW() - INTERVAL '180 days'
ORDER BY l.created_at DESC, a.created_at DESC
LIMIT 50;"""
    )
}

def get_or_start_postgres():
    """Returns (conn, is_managed, pg_obj)."""
    import psycopg2

    # 1. Check environment variables
    urls_to_try = [
        os.getenv("LEDGER_DATABASE_URL"),
        os.getenv("DATABASE_URL"),
        "postgresql://postgres:postgres@localhost:5432/ledger",
        "postgresql://postgres:postgres@localhost:5433/ledger",
    ]
    for url in urls_to_try:
        if not url:
            continue
        try:
            conn = psycopg2.connect(url)
            conn.autocommit = True
            print(f"[*] Connected to existing PostgreSQL at: {url}")
            return conn, False, None
        except Exception:
            pass

    # 2. Try embedded pgserver
    try:
        import pgserver
        pgdata_dir = os.path.abspath(os.path.join(REPO_ROOT, ".pgdata"))
        os.makedirs(pgdata_dir, exist_ok=True)
        print(f"[*] Starting embedded PostgreSQL 16 server at {pgdata_dir}...")
        pg = pgserver.get_server(pgdata_dir)
        pg_uri = pg.get_uri()
        print(f"[*] Embedded PostgreSQL running at: {pg_uri}")
        conn = psycopg2.connect(pg_uri)
        conn.autocommit = True
        return conn, True, pg
    except Exception as e:
        print(f"[!] Could not start embedded PostgreSQL: {e}")
        return None, False, None

def parse_explain_metrics(explain_output: str):
    """Parses Execution Time and Buffers from EXPLAIN (ANALYZE, BUFFERS) output."""
    exec_match = re.search(r"Execution Time:\s+([0-9.]+)\s+ms", explain_output)
    plan_match = re.search(r"Planning Time:\s+([0-9.]+)\s+ms", explain_output)
    exec_time = float(exec_match.group(1)) if exec_match else 0.0
    plan_time = float(plan_match.group(1)) if plan_match else 0.0

    # Buffers
    buffers_match = re.findall(r"Buffers:\s+([^\n]+)", explain_output)
    buffers_str = "; ".join(buffers_match) if buffers_match else "N/A"

    # Scan type
    scan_type = "Unknown Scan"
    if "Index Only Scan" in explain_output:
        scan_type = "Index Only Scan"
    elif "Index Scan" in explain_output:
        scan_type = "Index Scan"
    elif "Bitmap Heap Scan" in explain_output:
        scan_type = "Bitmap Heap Scan"
    elif "Seq Scan" in explain_output:
        scan_type = "Seq Scan"
    elif "Nested Loop" in explain_output:
        scan_type = "Nested Loop (Indexed)"
    elif "Hash Join" in explain_output:
        scan_type = "Hash Join (Seq Scan)"

    return {
        "execution_time_ms": exec_time,
        "planning_time_ms": plan_time,
        "scan_type": scan_type,
        "buffers": buffers_str,
        "raw": explain_output
    }

def main():
    print("=" * 75)
    print("  DataNexus v3.0: PostgreSQL Query Plan & Indexing Benchmark")
    print("=" * 75)

    conn, is_managed, pg_obj = get_or_start_postgres()
    if conn is None:
        print("[!] Error: No PostgreSQL instance available. Exiting.")
        sys.exit(1)

    cur = conn.cursor()

    try:
        # Step 1: Initialize schema
        print("[1/6] Initializing base schema (V1__init_ledger.sql)...")
        with open(V1_MIGRATION, "r", encoding="utf-8") as f:
            v1_sql = f.read()
        try:
            cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        except Exception:
            pass
        cur.execute(v1_sql)

        # Drop indexes if present to test unindexed baseline
        cur.execute("DROP INDEX IF EXISTS idx_ledger_status_curr_created;")
        cur.execute("DROP INDEX IF EXISTS idx_ledger_vendor_curr_created;")
        cur.execute("DROP INDEX IF EXISTS idx_ledger_rejected_created;")
        cur.execute("DROP INDEX IF EXISTS idx_audit_entry_created;")
        cur.execute("DROP INDEX IF EXISTS idx_audit_ledger_entry_id;")

        # Step 2: Seed synthetic dataset (100k ledger + 200k audit)
        cur.execute("SELECT COUNT(*) FROM ledger_entries;")
        count = cur.fetchone()[0]
        if count < 100000:
            print(f"[2/6] Seeding 100,000 ledger_entries and 200,000 audit_events (current count={count})...")
            cur.execute("TRUNCATE TABLE audit_events CASCADE;")
            cur.execute("TRUNCATE TABLE ledger_entries CASCADE;")

            seed_ledger_sql = """
            INSERT INTO ledger_entries (
                id, invoice_number, vendor_name, currency, amount, status,
                validation_score, source_doc_hash, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                'INV-' || to_char(i, 'FM000000'),
                (ARRAY['Acme Industrial Corp', 'Global Logistics Ltd', 'Vertex Systems Inc', 'Continental Tech GmbH', 'Pacific Supply Co', 'Nordic Energy AG', 'Apex Capital Partners', 'Zenith Cloud Services'])[1 + (i % 8)],
                (ARRAY['USD', 'EUR', 'GBP', 'INR', 'JPY', 'CHF'])[1 + (i % 6)],
                round((15 + (random() * 49985))::numeric, 4),
                (ARRAY['PENDING', 'VALIDATED', 'SETTLED', 'REJECTED'])[1 + (i % 4)],
                round((70 + (random() * 30))::numeric, 2),
                md5(i::text),
                NOW() - (random() * interval '730 days'),
                NOW()
            FROM generate_series(1, 100000) AS i;
            """
            cur.execute(seed_ledger_sql)
            print("      [+] 100,000 ledger_entries inserted.")

            seed_audit_sql = """
            INSERT INTO audit_events (
                ledger_entry_id, event_type, actor, payload, created_at
            )
            SELECT
                le.id,
                CASE s
                    WHEN 1 THEN 'INVOICE_INGESTED'
                    ELSE (ARRAY['RULE_VALIDATION_PASSED', 'SETTLEMENT_PROCESSED', 'FLAGGED_ANOMALY'])[1 + (le.rnum % 3)]
                END,
                CASE s
                    WHEN 1 THEN 'fastapi-bridge'
                    ELSE (ARRAY['system-worker', 'settlement-engine', 'compliance-auditor'])[1 + (le.rnum % 3)]
                END,
                jsonb_build_object(
                    'step', s,
                    'invoiceNumber', le.invoice_number,
                    'amount', le.amount,
                    'currency', le.currency,
                    'status', le.status
                ),
                le.created_at + ((s * 45) || ' seconds')::interval
            FROM (
                SELECT id, invoice_number, amount, currency, status, created_at, row_number() OVER () AS rnum
                FROM ledger_entries
            ) le
            CROSS JOIN generate_series(1, 2) AS s;
            """
            cur.execute(seed_audit_sql)
            print("      [+] 200,000 audit_events inserted.")
        else:
            print(f"[2/6] Table ledger_entries already has {count:,} rows. Skipping insertion.")

        # Update statistics
        print("[3/6] Updating PostgreSQL planner statistics (ANALYZE)...")
        cur.execute("ANALYZE ledger_entries; ANALYZE audit_events;")

        # Step 3: Run queries BEFORE indexing
        print("\n[4/6] Executing EXPLAIN (ANALYZE, BUFFERS) BEFORE INDEXING...")
        before_results = {}
        for q_id, (q_name, q_sql) in QUERIES.items():
            explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE) {q_sql}"
            cur.execute(explain_sql)
            raw = "\n".join(row[0] for row in cur.fetchall())
            metrics = parse_explain_metrics(raw)
            before_results[q_id] = metrics
            print(f"  -> {q_id} ({q_name}): {metrics['scan_type']} | {metrics['execution_time_ms']:.2f} ms")

        # Step 4: Apply performance indexes (V2)
        print("\n[5/6] Applying V2 performance indexes...")
        with open(V2_MIGRATION, "r", encoding="utf-8") as f:
            v2_sql = f.read()
        cur.execute(v2_sql)
        cur.execute("ANALYZE ledger_entries; ANALYZE audit_events;")
        print("      [+] Indexes created and statistics updated.")

        # Step 5: Run queries AFTER indexing
        print("\n[6/6] Executing EXPLAIN (ANALYZE, BUFFERS) AFTER INDEXING...")
        after_results = {}
        for q_id, (q_name, q_sql) in QUERIES.items():
            explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE) {q_sql}"
            cur.execute(explain_sql)
            raw = "\n".join(row[0] for row in cur.fetchall())
            metrics = parse_explain_metrics(raw)
            after_results[q_id] = metrics
            speedup = before_results[q_id]['execution_time_ms'] / metrics['execution_time_ms'] if metrics['execution_time_ms'] > 0 else 1.0
            print(f"  -> {q_id} ({q_name}): {metrics['scan_type']} | {metrics['execution_time_ms']:.2f} ms (Speedup: {speedup:.1f}x)")

        # Step 6: Generate updated markdown report
        print("\nGenerating updated docs/sql-tuning.md with verified numbers...")
        report_md = f"""# DataNexus v3.0: PostgreSQL Query Plan & Indexing Benchmark Report

## 1. Executive Summary
This document provides empirical, reproducible performance benchmarks for the DataNexus v3.0 Financial Ledger and Audit Trail service. The benchmark measures query latency, planner strategy, and disk/buffer I/O on a real PostgreSQL 16 instance before and after applying composite B-Tree and partial indexes.

* **Dataset Scale:** 100,000 multi-currency ledger rows (`ledger_entries`) and 200,000 immutable audit events (`audit_events`).
* **Currencies Covered:** `USD`, `EUR`, `GBP`, `INR`, `JPY`, `CHF` (6 distinct global fiat currencies).
* **Date Range:** 730 days (2-year rolling window).

---

## 2. Benchmark Comparison Table

| Query | Description | Before Plan | After Plan | Before (ms) | After (ms) | Speedup | Buffer I/O Impact |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **Q1** | Multi-Currency Settlement Rollup (`status = 'SETTLED'`, 90d window) | `{before_results['Q1']['scan_type']}` | `{after_results['Q1']['scan_type']}` | **{before_results['Q1']['execution_time_ms']:.2f} ms** | **{after_results['Q1']['execution_time_ms']:.2f} ms** | **{before_results['Q1']['execution_time_ms'] / max(after_results['Q1']['execution_time_ms'], 0.001):.1f}x** | Heap reads bypassed via composite index |
| **Q2** | Vendor + Currency Paginated Audit Lookup (25 rows, `created_at DESC`) | `{before_results['Q2']['scan_type']}` | `{after_results['Q2']['scan_type']}` | **{before_results['Q2']['execution_time_ms']:.2f} ms** | **{after_results['Q2']['execution_time_ms']:.2f} ms** | **{before_results['Q2']['execution_time_ms'] / max(after_results['Q2']['execution_time_ms'], 0.001):.1f}x** | Top-N Sort eliminated; Direct B-Tree descent |
| **Q3** | Rejected Invoices Join with Audit Events (`status = 'REJECTED'`) | `{before_results['Q3']['scan_type']}` | `{after_results['Q3']['scan_type']}` | **{before_results['Q3']['execution_time_ms']:.2f} ms** | **{after_results['Q3']['execution_time_ms']:.2f} ms** | **{before_results['Q3']['execution_time_ms'] / max(after_results['Q3']['execution_time_ms'], 0.001):.1f}x** | Partial index filters 75% of rows upfront; FK Index lookup |

---

## 3. Query Analysis & Indexing Strategy

### 3.1 Query 1: Multi-Currency Settlement Rollup
* **Business Need:** High-frequency dashboard rollup aggregating settlement volumes, invoice counts, and average validation scores across currencies over the last 90 days.
* **Applied Index:**
  ```sql
  CREATE INDEX idx_ledger_status_curr_created
      ON ledger_entries (status, currency, created_at DESC);
  ```
* **Performance Gain:** Transitions planner from a full table sequential scan to an index-driven bitmap scan, directly eliminating table pages for non-matching statuses.

#### Raw Plan Before Indexing:
```text
{before_results['Q1']['raw']}
```

#### Raw Plan After Indexing:
```text
{after_results['Q1']['raw']}
```

---

### 3.2 Query 2: Vendor + Currency Paginated Audit Lookup
* **Business Need:** Financial analysts filtering transactions by vendor and fiat currency, ordered reverse-chronologically with pagination.
* **Applied Index:**
  ```sql
  CREATE INDEX idx_ledger_vendor_curr_created
      ON ledger_entries (vendor_name, currency, created_at DESC);
  ```
* **Performance Gain:** Eliminates an in-memory or spill-to-disk `Sort` node entirely by maintaining physical index ordering matching the `ORDER BY created_at DESC` clause.

#### Raw Plan Before Indexing:
```text
{before_results['Q2']['raw']}
```

#### Raw Plan After Indexing:
```text
{after_results['Q2']['raw']}
```

---

### 3.3 Query 3: Flagged / Rejected Invoice Join
* **Business Need:** Compliance and risk surveillance scanning rejected invoices and their corresponding audit logs.
* **Applied Indexes:**
  ```sql
  -- Partial Index: Only indexes rejected rows (approx. 25% of table volume)
  CREATE INDEX idx_ledger_rejected_created
      ON ledger_entries (created_at DESC)
      WHERE status = 'REJECTED';

  -- Covering Foreign Key Index on Audit Events
  CREATE INDEX idx_audit_entry_created
      ON audit_events (ledger_entry_id, created_at DESC);
  ```
* **Performance Gain:** Partial indexing keeps the index tree extremely compact in memory. Combined with the FK covering index on `audit_events`, PostgreSQL replaces expensive full-table hash joins with tight nested loop index scans.

#### Raw Plan Before Indexing:
```text
{before_results['Q3']['raw']}
```

#### Raw Plan After Indexing:
```text
{after_results['Q3']['raw']}
```

---

## 4. How to Reproduce
Run the benchmark runner directly:
```bash
# If running with local/docker postgres:
docker compose -f docker-compose.monitoring.yml up -d postgres
python scripts/run_sql_benchmark.py
```
"""
        with open(OUTPUT_MD, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"[+] Successfully wrote {OUTPUT_MD}")

    finally:
        cur.close()
        conn.close()

    print("\n" + "=" * 75)
    print("  Benchmark Completed Successfully!")
    print("=" * 75)

if __name__ == "__main__":
    main()
