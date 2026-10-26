from sqlalchemy import text, Engine

POSTGRESQL_VIEWS_SQL = [
    # 1. Daily Ingestion View
    """
    CREATE OR REPLACE VIEW v_daily_ingestion AS
    SELECT 
        CAST(created_at AS DATE) AS ingestion_date,
        COUNT(*) AS total_documents,
        SUM(file_size) AS total_bytes,
        ROUND(CAST(AVG(page_count) AS NUMERIC), 1) AS avg_page_count,
        SUM(CASE WHEN is_duplicate = TRUE THEN 1 ELSE 0 END) AS duplicate_count
    FROM documents
    GROUP BY CAST(created_at AS DATE);
    """,

    # 2. Processing Performance View
    """
    CREATE OR REPLACE VIEW v_processing_performance AS
    SELECT 
        file_type,
        COUNT(*) AS total_processed,
        SUM(CASE WHEN final_status = 'completed' THEN 1 ELSE 0 END) AS success_count,
        SUM(CASE WHEN final_status = 'failed' THEN 1 ELSE 0 END) AS failure_count,
        ROUND(CAST(AVG(processing_time_ms) AS NUMERIC), 0) AS avg_duration_ms,
        SUM(CASE WHEN ocr_invoked = TRUE THEN 1 ELSE 0 END) AS ocr_count,
        SUM(CASE WHEN indexing_succeeded = TRUE THEN 1 ELSE 0 END) AS indexed_count
    FROM fact_document_processing
    GROUP BY file_type;
    """,

    # 3. Invoice Spend By Vendor & Currency View
    """
    CREATE OR REPLACE VIEW v_invoice_spend_by_vendor AS
    SELECT 
        v.vendor_name,
        v.category AS vendor_category,
        fi.currency,
        COUNT(fi.invoice_key) AS invoice_count,
        ROUND(CAST(SUM(fi.subtotal) AS NUMERIC), 2) AS total_subtotal,
        ROUND(CAST(SUM(fi.tax_amount) AS NUMERIC), 2) AS total_tax,
        ROUND(CAST(SUM(fi.total_amount) AS NUMERIC), 2) AS total_spend,
        ROUND(CAST(AVG(fi.extraction_confidence) AS NUMERIC), 3) AS avg_confidence
    FROM fact_invoice fi
    JOIN dim_vendor v ON fi.vendor_key = v.vendor_key
    GROUP BY v.vendor_name, v.category, fi.currency;
    """,

    # 4. Overdue Invoices View
    """
    CREATE OR REPLACE VIEW v_overdue_invoices AS
    SELECT 
        fi.invoice_number,
        v.vendor_name,
        fi.currency,
        fi.total_amount,
        fi.payment_status,
        fi.days_overdue,
        d.full_date AS invoice_date,
        dd.full_date AS due_date,
        fi.document_id
    FROM fact_invoice fi
    JOIN dim_vendor v ON fi.vendor_key = v.vendor_key
    JOIN dim_date d ON fi.invoice_date_key = d.date_key
    LEFT JOIN dim_date dd ON fi.due_date_key = dd.date_key
    WHERE fi.is_overdue = TRUE OR fi.payment_status = 'Overdue';
    """,

    # 5. Data Quality Scorecard View
    """
    CREATE OR REPLACE VIEW v_data_quality_scorecard AS
    SELECT 
        rule_name,
        rule_category,
        COUNT(*) AS total_evaluations,
        SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) AS passed_count,
        SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS failed_count,
        SUM(CASE WHEN status = 'warning' THEN 1 ELSE 0 END) AS warning_count,
        ROUND(CAST(100.0 * SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) AS NUMERIC), 1) AS pass_percentage
    FROM data_quality_results
    GROUP BY rule_name, rule_category;
    """,

    # 6. Pipeline Freshness View
    """
    CREATE OR REPLACE VIEW v_pipeline_freshness AS
    SELECT 
        pipeline_name,
        COUNT(*) AS total_runs,
        MAX(created_at) AS last_run_at,
        SUM(rows_read) AS total_rows_read,
        SUM(rows_inserted + rows_updated) AS total_rows_processed,
        SUM(rows_rejected) AS total_rows_rejected,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_runs
    FROM pipeline_runs
    GROUP BY pipeline_name;
    """,

    # 7. Search Indexing Coverage View
    """
    CREATE OR REPLACE VIEW v_indexing_coverage AS
    SELECT 
        COUNT(DISTINCT d.id) AS total_documents,
        SUM(CASE WHEN d.status = 'completed' THEN 1 ELSE 0 END) AS completed_documents,
        COUNT(DISTINCT dc.document_id) AS indexed_documents,
        COUNT(dc.id) AS total_chunks_indexed,
        ROUND(CAST(100.0 * COUNT(DISTINCT dc.document_id) / NULLIF(SUM(CASE WHEN d.status = 'completed' THEN 1 ELSE 0 END), 0) AS NUMERIC), 1) AS coverage_percentage
    FROM documents d
    LEFT JOIN document_chunks dc ON d.id = dc.document_id AND dc.indexed_in_es = TRUE;
    """
]

SQLITE_VIEWS_SQL = [
    # 1. Daily Ingestion View
    """
    CREATE VIEW IF NOT EXISTS v_daily_ingestion AS
    SELECT 
        substr(created_at, 1, 10) AS ingestion_date,
        COUNT(*) AS total_documents,
        SUM(file_size) AS total_bytes,
        ROUND(AVG(page_count), 1) AS avg_page_count,
        SUM(CASE WHEN is_duplicate = 1 THEN 1 ELSE 0 END) AS duplicate_count
    FROM documents
    GROUP BY substr(created_at, 1, 10);
    """,

    # 2. Processing Performance View
    """
    CREATE VIEW IF NOT EXISTS v_processing_performance AS
    SELECT 
        file_type,
        COUNT(*) AS total_processed,
        SUM(CASE WHEN final_status = 'completed' THEN 1 ELSE 0 END) AS success_count,
        SUM(CASE WHEN final_status = 'failed' THEN 1 ELSE 0 END) AS failure_count,
        ROUND(AVG(processing_time_ms), 0) AS avg_duration_ms,
        SUM(CASE WHEN ocr_invoked = 1 THEN 1 ELSE 0 END) AS ocr_count,
        SUM(CASE WHEN indexing_succeeded = 1 THEN 1 ELSE 0 END) AS indexed_count
    FROM fact_document_processing
    GROUP BY file_type;
    """,

    # 3. Invoice Spend By Vendor & Currency View
    """
    CREATE VIEW IF NOT EXISTS v_invoice_spend_by_vendor AS
    SELECT 
        v.vendor_name,
        v.category AS vendor_category,
        fi.currency,
        COUNT(fi.invoice_key) AS invoice_count,
        ROUND(SUM(fi.subtotal), 2) AS total_subtotal,
        ROUND(SUM(fi.tax_amount), 2) AS total_tax,
        ROUND(SUM(fi.total_amount), 2) AS total_spend,
        ROUND(AVG(fi.extraction_confidence), 3) AS avg_confidence
    FROM fact_invoice fi
    JOIN dim_vendor v ON fi.vendor_key = v.vendor_key
    GROUP BY v.vendor_name, v.category, fi.currency;
    """,

    # 4. Overdue Invoices View
    """
    CREATE VIEW IF NOT EXISTS v_overdue_invoices AS
    SELECT 
        fi.invoice_number,
        v.vendor_name,
        fi.currency,
        fi.total_amount,
        fi.payment_status,
        fi.days_overdue,
        d.full_date AS invoice_date,
        dd.full_date AS due_date,
        fi.document_id
    FROM fact_invoice fi
    JOIN dim_vendor v ON fi.vendor_key = v.vendor_key
    JOIN dim_date d ON fi.invoice_date_key = d.date_key
    LEFT JOIN dim_date dd ON fi.due_date_key = dd.date_key
    WHERE fi.is_overdue = 1 OR fi.payment_status = 'Overdue';
    """,

    # 5. Data Quality Scorecard View
    """
    CREATE VIEW IF NOT EXISTS v_data_quality_scorecard AS
    SELECT 
        rule_name,
        rule_category,
        COUNT(*) AS total_evaluations,
        SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) AS passed_count,
        SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS failed_count,
        SUM(CASE WHEN status = 'warning' THEN 1 ELSE 0 END) AS warning_count,
        ROUND(100.0 * SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pass_percentage
    FROM data_quality_results
    GROUP BY rule_name, rule_category;
    """,

    # 6. Pipeline Freshness View
    """
    CREATE VIEW IF NOT EXISTS v_pipeline_freshness AS
    SELECT 
        pipeline_name,
        COUNT(*) AS total_runs,
        MAX(created_at) AS last_run_at,
        SUM(rows_read) AS total_rows_read,
        SUM(rows_inserted + rows_updated) AS total_rows_processed,
        SUM(rows_rejected) AS total_rows_rejected,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_runs
    FROM pipeline_runs
    GROUP BY pipeline_name;
    """,

    # 7. Search Indexing Coverage View
    """
    CREATE VIEW IF NOT EXISTS v_indexing_coverage AS
    SELECT 
        COUNT(DISTINCT d.id) AS total_documents,
        SUM(CASE WHEN d.status = 'completed' THEN 1 ELSE 0 END) AS completed_documents,
        COUNT(DISTINCT dc.document_id) AS indexed_documents,
        COUNT(dc.id) AS total_chunks_indexed,
        ROUND(100.0 * COUNT(DISTINCT dc.document_id) / NULLIF(SUM(CASE WHEN d.status = 'completed' THEN 1 ELSE 0 END), 0), 1) AS coverage_percentage
    FROM documents d
    LEFT JOIN document_chunks dc ON d.id = dc.document_id AND dc.indexed_in_es = 1;
    """
]

def init_analytical_views(engine: Engine) -> None:
    """Create analytical SQL views across PostgreSQL and SQLite."""
    dialect = getattr(engine, "dialect", None)
    dialect_name = dialect.name if dialect else "sqlite"
    views_sql = POSTGRESQL_VIEWS_SQL if dialect_name == "postgresql" else SQLITE_VIEWS_SQL

    with engine.begin() as conn:
        for view_sql in views_sql:
            try:
                conn.execute(text(view_sql))
            except Exception as e:
                # Log or tolerate if already exists or dialect specific
                print(f"Notice on view init ({dialect_name}): {e}")
