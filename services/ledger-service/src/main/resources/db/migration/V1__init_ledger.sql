-- =============================================================================
-- V1__init_ledger.sql: Schema for Immutable Financial Ledger & Audit Trail
-- =============================================================================

CREATE TABLE IF NOT EXISTS ledger_entries (
    id UUID PRIMARY KEY,
    invoice_number VARCHAR(100) NOT NULL,
    vendor_name VARCHAR(255) NOT NULL,
    currency CHAR(3) NOT NULL,
    amount NUMERIC(18, 4) NOT NULL,
    status VARCHAR(50) NOT NULL,
    validation_score NUMERIC(5, 2),
    source_doc_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    ledger_entry_id UUID NOT NULL REFERENCES ledger_entries(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    actor VARCHAR(100) NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
