-- =============================================================================
-- DataNexus v3.0: PostgreSQL Query Plan & Indexing Benchmark Script
-- Seeds 100,000 ledger rows & 200,000 audit rows, runs EXPLAIN ANALYZE before/after
-- =============================================================================

\timing on

-- 1. Ensure clean schema state
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing indexes if re-running
DROP INDEX IF EXISTS idx_ledger_status_curr_created;
DROP INDEX IF EXISTS idx_ledger_vendor_curr_created;
DROP INDEX IF EXISTS idx_ledger_rejected_created;
DROP INDEX IF EXISTS idx_audit_entry_created;

TRUNCATE TABLE audit_events CASCADE;
TRUNCATE TABLE ledger_entries CASCADE;

-- 2. Seed 100,000 synthetic multi-currency ledger rows
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

-- 3. Seed 200,000 audit_events rows (2 events per ledger entry)
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

-- 4. Update PostgreSQL statistics
ANALYZE ledger_entries;
ANALYZE audit_events;

-- =============================================================================
-- BENCHMARKS BEFORE INDEXING
-- =============================================================================

\echo '=== [BEFORE INDEXING] Query 1: Settlement Rollup ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT
    currency,
    status,
    COUNT(*) AS entry_count,
    SUM(amount) AS total_volume,
    ROUND(AVG(validation_score), 2) AS avg_score
FROM ledger_entries
WHERE status = 'SETTLED'
  AND created_at >= NOW() - INTERVAL '90 days'
GROUP BY currency, status
ORDER BY total_volume DESC;

\echo '=== [BEFORE INDEXING] Query 2: Vendor + Currency Paginated Lookup ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT
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
LIMIT 25 OFFSET 0;

\echo '=== [BEFORE INDEXING] Query 3: Join Filtered by Status = REJECTED ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT
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
LIMIT 50;

-- =============================================================================
-- APPLY PERFORMANCE INDEXES (Flyway V2)
-- =============================================================================

CREATE INDEX idx_ledger_status_curr_created
    ON ledger_entries (status, currency, created_at DESC);

CREATE INDEX idx_ledger_vendor_curr_created
    ON ledger_entries (vendor_name, currency, created_at DESC);

CREATE INDEX idx_ledger_rejected_created
    ON ledger_entries (created_at DESC)
    WHERE status = 'REJECTED';

CREATE INDEX idx_audit_entry_created
    ON audit_events (ledger_entry_id, created_at DESC);

-- Update statistics post-indexing
ANALYZE ledger_entries;
ANALYZE audit_events;

-- =============================================================================
-- BENCHMARKS AFTER INDEXING
-- =============================================================================

\echo '=== [AFTER INDEXING] Query 1: Settlement Rollup ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT
    currency,
    status,
    COUNT(*) AS entry_count,
    SUM(amount) AS total_volume,
    ROUND(AVG(validation_score), 2) AS avg_score
FROM ledger_entries
WHERE status = 'SETTLED'
  AND created_at >= NOW() - INTERVAL '90 days'
GROUP BY currency, status
ORDER BY total_volume DESC;

\echo '=== [AFTER INDEXING] Query 2: Vendor + Currency Paginated Lookup ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT
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
LIMIT 25 OFFSET 0;

\echo '=== [AFTER INDEXING] Query 3: Join Filtered by Status = REJECTED ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS, VERBOSE)
SELECT
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
LIMIT 50;
