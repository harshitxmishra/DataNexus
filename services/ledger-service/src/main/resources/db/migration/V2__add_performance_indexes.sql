-- =============================================================================
-- V2__add_performance_indexes.sql: Enterprise Performance Optimization Indexes
-- =============================================================================

-- Composite B-Tree index for settlement rollup queries filtered by status, currency, and date
CREATE INDEX IF NOT EXISTS idx_ledger_status_curr_created
    ON ledger_entries (status, currency, created_at DESC);

-- Composite B-Tree index for vendor + currency paginated audit lookups
CREATE INDEX IF NOT EXISTS idx_ledger_vendor_curr_created
    ON ledger_entries (vendor_name, currency, created_at DESC);

-- Partial index for high-priority rejected/flagged invoice auditing
CREATE INDEX IF NOT EXISTS idx_ledger_rejected_created
    ON ledger_entries (created_at DESC)
    WHERE status = 'REJECTED';

-- Covering foreign key index on audit_events to eliminate sequential scans on ledger joins
CREATE INDEX IF NOT EXISTS idx_audit_entry_created
    ON audit_events (ledger_entry_id, created_at DESC);
