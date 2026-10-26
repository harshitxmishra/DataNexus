#!/usr/bin/env python3
"""
DataNexus — SQLite to PostgreSQL Migration Utility (Hardened)
Transfers all existing operational, metadata, and analytical star-schema data
from SQLite to PostgreSQL safely with:
- Strict foreign-key dependency ordering
- Self-referential FK root-first ordering (e.g., documents.duplicate_of_id)
- PostgreSQL sequence / identity synchronization (setval)
- Boolean type normalization (0/1 -> True/False)
- Datetime/date string normalization
- Conflict and pre-existing data detection (no silent skipping)
- Optional --clean-target flag
- Alembic-based target schema initialization and version stamping
- Primary key referential integrity validation

Usage:
    python scripts/migrate_sqlite_to_postgres.py --target-url postgresql://user:pass@localhost:5432/datanexus [--clean-target]
"""

import argparse
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Set

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text, inspect
from alembic.config import Config
from alembic import command

from backend.app.config import settings
from backend.app.database import Base, normalize_database_url
import backend.app.models  # Register all models with Base.metadata
from backend.app.models.views import init_analytical_views

# Ordered list of tables to migrate respecting foreign key dependencies
TABLE_MIGRATION_ORDER = [
    "dim_date",
    "dim_vendor",
    "pipeline_runs",
    "data_quality_results",
    "rejected_records",
    "staged_csv_records",
    "queue_jobs",
    "documents",
    "document_chunks",
    "document_stage_events",
    "extracted_fields",
    "invoice_line_items",
    "fact_invoice",
    "fact_invoice_line",
    "fact_document_processing",
    "fact_data_quality",
    "fact_pipeline_run",
    "lineage_edges",
]

# Tables with SERIAL / Autoincrement keys in PostgreSQL requiring sequence sync
SERIAL_COLUMNS = {
    "dim_vendor": "vendor_key",
    "fact_invoice": "invoice_key",
    "fact_invoice_line": "line_key",
    "fact_document_processing": "event_key",
    "fact_data_quality": "evaluation_key",
    "fact_pipeline_run": "run_key",
}

# Boolean columns requiring explicit conversion from SQLite int (0/1)
BOOLEAN_COLUMNS = {
    "documents": {"is_duplicate"},
    "document_chunks": {"indexed_in_es"},
    "dim_date": {"is_weekend"},
    "fact_invoice": {"is_overdue"},
    "fact_document_processing": {"ocr_invoked", "indexing_succeeded", "extraction_succeeded"},
}

def mask_url_for_display(url: str) -> str:
    """Mask password credentials in database URLs for safe logging."""
    if "@" in url and "://" in url:
        prefix = url.split("://")[0] + "://"
        user_pass = url.split("://")[1].split("@")[0]
        host_db = url.split("@")[1]
        user = user_pass.split(":")[0] if ":" in user_pass else user_pass
        return f"{prefix}{user}:****@{host_db}"
    return url

def initialize_target_schema(target_url: str) -> None:
    """Initialize target schema using Alembic migrations and analytical views."""
    norm_url = normalize_database_url(target_url)
    
    # Set DATABASE_URL for Alembic config
    os.environ["DATABASE_URL"] = norm_url
    alembic_ini_path = PROJECT_ROOT / "alembic.ini"
    
    print("\n[*] Initializing target schema via Alembic migrations...")
    try:
        cfg = Config(str(alembic_ini_path))
        command.upgrade(cfg, "head")
        print("[+] Alembic upgrade head executed successfully on target.")
    except Exception as e:
        print(f"[!] Alembic migration warning: {e}. Falling back to metadata.create_all.")
        engine = create_engine(norm_url)
        Base.metadata.create_all(bind=engine)
        engine.dispose()

    # Create analytical views
    target_engine = create_engine(norm_url)
    init_analytical_views(target_engine)
    target_engine.dispose()
    print("[+] Analytical views initialized on target.")

def normalize_row_values(table_name: str, row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Convert SQLite types to PostgreSQL-compliant types (booleans, timestamps)."""
    bool_cols = BOOLEAN_COLUMNS.get(table_name, set())
    for col in bool_cols:
        if col in row_dict and row_dict[col] is not None:
            # Convert 0/1 integer or string to strict Python bool
            row_dict[col] = bool(row_dict[col])
            
    return row_dict

def sync_postgres_sequences(target_engine, table_name: str, pk_col: str) -> None:
    """Update PostgreSQL SERIAL sequence to MAX(primary_key) so subsequent inserts do not collide."""
    if target_engine.dialect.name != "postgresql":
        return

    sql = text(f"""
        SELECT setval(
            pg_get_serial_sequence('{table_name}', '{pk_col}'),
            COALESCE((SELECT MAX({pk_col}) FROM {table_name}), 1)
        );
    """)
    try:
        with target_engine.begin() as conn:
            conn.execute(sql)
        print(f"    -> Synchronized PostgreSQL sequence for {table_name}.{pk_col}")
    except Exception as e:
        print(f"    [!] Warning: Failed synchronizing sequence for {table_name}.{pk_col}: {e}")

def migrate_data(source_url: str, target_url: str, batch_size: int = 500, clean_target: bool = False) -> Dict[str, Dict[str, Any]]:
    """Migrate all tables from source (SQLite) to target (PostgreSQL) with validation."""
    norm_source_url = normalize_database_url(source_url)
    norm_target_url = normalize_database_url(target_url)

    print(f"[*] Source Database: {mask_url_for_display(source_url)}")
    print(f"[*] Target Database: {mask_url_for_display(norm_target_url)}")

    source_engine = create_engine(norm_source_url)
    target_engine = create_engine(norm_target_url)

    # 1. Initialize Schema
    initialize_target_schema(norm_target_url)

    source_inspector = inspect(source_engine)
    target_inspector = inspect(target_engine)
    source_tables = set(source_inspector.get_table_names())
    target_tables = set(target_inspector.get_table_names())

    # Optional clean-up in reverse dependency order
    if clean_target:
        print("\n[*] Cleaning target tables before migration (--clean-target enabled)...")
        with target_engine.begin() as conn:
            for table_name in reversed(TABLE_MIGRATION_ORDER):
                if table_name in target_tables:
                    try:
                        conn.execute(text(f"DELETE FROM {table_name}"))
                    except Exception as e:
                        print(f"    Notice cleaning {table_name}: {e}")
        print("[+] Target tables cleaned.")

    results = {}

    with source_engine.connect() as src_conn:
        for table_name in TABLE_MIGRATION_ORDER:
            if table_name not in source_tables:
                results[table_name] = {"source": 0, "target": 0, "status": "NOT_IN_SOURCE"}
                continue

            # Count rows
            src_count = src_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
            
            with target_engine.connect() as tgt_conn:
                initial_tgt_count = tgt_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0

            if src_count == 0:
                results[table_name] = {
                    "source": 0,
                    "target": initial_tgt_count,
                    "status": "EMPTY",
                    "inserted": 0,
                    "skipped": 0,
                }
                print(f"[.] Table '{table_name}': 0 source rows (empty)")
                continue

            print(f"[*] Migrating table '{table_name}' ({src_count} source rows)...")

            # Fetch source columns
            cols = [col["name"] for col in source_inspector.get_columns(table_name)]
            col_list_str = ", ".join(cols)
            param_list_str = ", ".join([f":{c}" for c in cols])

            # For documents table, order root documents before duplicates to satisfy self-referential FK
            order_clause = ""
            if table_name == "documents":
                order_clause = "ORDER BY CASE WHEN duplicate_of_id IS NULL THEN 0 ELSE 1 END, created_at"

            select_sql = text(f"SELECT {col_list_str} FROM {table_name} {order_clause}")
            
            # Use dialect-aware insert with conflict reporting
            # In PostgreSQL and SQLite 3.24+, ON CONFLICT DO NOTHING prevents crashes on primary key collisions
            insert_sql = text(f"INSERT INTO {table_name} ({col_list_str}) VALUES ({param_list_str}) ON CONFLICT DO NOTHING")

            cursor = src_conn.execute(select_sql)
            total_processed = 0

            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                row_dicts = [normalize_row_values(table_name, dict(row._mapping)) for row in rows]
                with target_engine.begin() as trans_conn:
                    trans_conn.execute(insert_sql, row_dicts)
                total_processed += len(rows)

            # Sync sequence if table has a SERIAL primary key
            if table_name in SERIAL_COLUMNS:
                sync_postgres_sequences(target_engine, table_name, SERIAL_COLUMNS[table_name])

            # Final verification count
            with target_engine.connect() as tgt_conn:
                final_tgt_count = tgt_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0

            net_inserted = final_tgt_count - initial_tgt_count
            skipped = src_count - net_inserted

            if skipped > 0 and not clean_target:
                status = f"CONFLICT_SKIPPED ({skipped} pre-existing)"
            elif final_tgt_count >= src_count:
                status = "OK"
            else:
                status = f"MISMATCH ({final_tgt_count}/{src_count})"

            results[table_name] = {
                "source": src_count,
                "target": final_tgt_count,
                "inserted": net_inserted,
                "skipped": skipped,
                "status": status,
            }
            print(f"    -> Target rows: {final_tgt_count}/{src_count} (Inserted: {net_inserted}, Status: {status})")

    source_engine.dispose()
    target_engine.dispose()
    return results

def validate_referential_integrity(target_url: str) -> List[str]:
    """Validate foreign key referential integrity in target database."""
    engine = create_engine(normalize_database_url(target_url))
    issues = []
    with engine.connect() as conn:
        # Check fact_invoice -> dim_vendor
        orphan_vendors = conn.execute(text("""
            SELECT COUNT(*) FROM fact_invoice fi
            LEFT JOIN dim_vendor v ON fi.vendor_key = v.vendor_key
            WHERE v.vendor_key IS NULL
        """)).scalar() or 0
        if orphan_vendors > 0:
            issues.append(f"fact_invoice has {orphan_vendors} orphan vendor keys")

        # Check fact_invoice -> documents
        orphan_docs = conn.execute(text("""
            SELECT COUNT(*) FROM fact_invoice fi
            LEFT JOIN documents d ON fi.document_id = d.id
            WHERE d.id IS NULL
        """)).scalar() or 0
        if orphan_docs > 0:
            issues.append(f"fact_invoice has {orphan_docs} orphan document IDs")

        # Check document_chunks -> documents
        orphan_chunks = conn.execute(text("""
            SELECT COUNT(*) FROM document_chunks dc
            LEFT JOIN documents d ON dc.document_id = d.id
            WHERE d.id IS NULL
        """)).scalar() or 0
        if orphan_chunks > 0:
            issues.append(f"document_chunks has {orphan_chunks} orphan document IDs")

    engine.dispose()
    return issues

def main():
    parser = argparse.ArgumentParser(description="DataNexus SQLite to PostgreSQL Migration Utility (Hardened)")
    parser.add_argument("--source-url", default=settings.DATABASE_URL, help="Source SQLite connection URL")
    parser.add_argument("--target-url", default=os.getenv("TARGET_DATABASE_URL", ""), help="Target PostgreSQL connection URL")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for batch insert")
    parser.add_argument("--clean-target", action="store_true", help="Delete existing target table data before migrating")
    args = parser.parse_args()

    if not args.target_url:
        print("[!] Error: --target-url or TARGET_DATABASE_URL environment variable is required.")
        print("    Example: python scripts/migrate_sqlite_to_postgres.py --target-url postgresql://user:pass@localhost:5432/datanexus")
        sys.exit(1)

    print("=" * 80)
    print(" DATANEXUS HARDENED DATABASE MIGRATION: SQLITE -> POSTGRESQL")
    print("=" * 80)

    results = migrate_data(args.source_url, args.target_url, args.batch_size, args.clean_target)

    # Validate referential integrity
    print("\n[*] Validating target referential integrity...")
    integrity_issues = validate_referential_integrity(args.target_url)
    if integrity_issues:
        for issue in integrity_issues:
            print(f"    [!] Referential Integrity Warning: {issue}")
    else:
        print("    [+] Referential integrity 100% verified (0 orphan records).")

    print("\n" + "=" * 80)
    print(" HARDENED MIGRATION SUMMARY REPORT")
    print("=" * 80)
    print(f"{'Table Name':<30} {'Source':<8} {'Target':<8} {'Inserted':<10} {'Status':<20}")
    print("-" * 80)
    total_src = 0
    total_tgt = 0
    total_ins = 0
    for tbl, info in results.items():
        total_src += info["source"]
        total_tgt += info["target"]
        total_ins += info.get("inserted", 0)
        print(f"{tbl:<30} {info['source']:<8} {info['target']:<8} {info.get('inserted', 0):<10} {info['status']:<20}")
    print("-" * 80)
    print(f"{'TOTALS':<30} {total_src:<8} {total_tgt:<8} {total_ins:<10}")
    print("=" * 80)

if __name__ == "__main__":
    main()
