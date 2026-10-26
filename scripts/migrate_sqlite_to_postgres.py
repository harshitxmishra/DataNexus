#!/usr/bin/env python3
"""
DataNexus — SQLite to PostgreSQL Migration Utility
Transfers all existing operational, metadata, and analytical star-schema data
from SQLite to PostgreSQL safely without data loss.

Usage:
    python scripts/migrate_sqlite_to_postgres.py --target-url postgresql://user:pass@localhost:5432/datanexus
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

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

def migrate_data(source_url: str, target_url: str, batch_size: int = 500) -> Dict[str, Dict[str, int]]:
    """Migrate all tables from source (SQLite) to target (PostgreSQL)."""
    norm_source_url = normalize_database_url(source_url)
    norm_target_url = normalize_database_url(target_url)

    print(f"[*] Source Database: {source_url}")
    # Mask password in target URL for log safety
    safe_target_url = norm_target_url
    if "@" in safe_target_url and "://" in safe_target_url:
        prefix = safe_target_url.split("://")[0] + "://"
        user_pass = safe_target_url.split("://")[1].split("@")[0]
        host_db = safe_target_url.split("@")[1]
        user = user_pass.split(":")[0] if ":" in user_pass else user_pass
        safe_target_url = f"{prefix}{user}:****@{host_db}"
    print(f"[*] Target Database: {safe_target_url}")

    source_engine = create_engine(norm_source_url)
    target_engine = create_engine(norm_target_url)

    # 1. Create target tables and views
    print("\n[*] Initializing target database schema...")
    Base.metadata.create_all(bind=target_engine)
    init_analytical_views(target_engine)
    print("[+] Target schema and analytical views initialized successfully.")

    # 2. Inspect available tables
    source_inspector = inspect(source_engine)
    source_tables = set(source_inspector.get_table_names())

    results = {}

    with source_engine.connect() as src_conn, target_engine.connect() as tgt_conn:
        for table_name in TABLE_MIGRATION_ORDER:
            if table_name not in source_tables:
                print(f"[-] Table '{table_name}' does not exist in source. Skipping.")
                continue

            # Count source rows
            src_count = src_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
            if src_count == 0:
                results[table_name] = {"source": 0, "target": 0, "status": "EMPTY"}
                print(f"[.] Table '{table_name}': 0 rows (empty)")
                continue

            print(f"[*] Migrating table '{table_name}' ({src_count} rows)...")

            # Fetch source columns
            cols = [col["name"] for col in source_inspector.get_columns(table_name)]
            col_list_str = ", ".join(cols)
            param_list_str = ", ".join([f":{c}" for c in cols])

            select_sql = text(f"SELECT {col_list_str} FROM {table_name}")
            insert_sql = text(f"INSERT INTO {table_name} ({col_list_str}) VALUES ({param_list_str}) ON CONFLICT DO NOTHING")

            # Copy data in batches
            cursor = src_conn.execute(select_sql)
            total_inserted = 0

            while True:
                rows = cursor.fetchmany(batch_size)
                if not rows:
                    break
                row_dicts = [dict(row._mapping) for row in rows]
                with target_engine.begin() as trans_conn:
                    trans_conn.execute(insert_sql, row_dicts)
                total_inserted += len(rows)

            tgt_count = tgt_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0
            status = "OK" if tgt_count == src_count else f"MISMATCH ({tgt_count}/{src_count})"
            results[table_name] = {"source": src_count, "target": tgt_count, "status": status}
            print(f"    -> Migrated {tgt_count}/{src_count} rows ({status})")

    return results

def main():
    parser = argparse.ArgumentParser(description="DataNexus SQLite to PostgreSQL Migration Utility")
    parser.add_argument("--source-url", default=settings.DATABASE_URL, help="Source SQLite connection URL")
    parser.add_argument("--target-url", default=os.getenv("TARGET_DATABASE_URL", ""), help="Target PostgreSQL connection URL")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for batch insert")
    args = parser.parse_args()

    if not args.target_url:
        print("[!] Error: --target-url or TARGET_DATABASE_URL environment variable is required.")
        print("    Example: python scripts/migrate_sqlite_to_postgres.py --target-url postgresql://user:pass@localhost:5432/datanexus")
        sys.exit(1)

    print("=" * 70)
    print(" DATANEXUS DATABASE MIGRATION: SQLITE -> POSTGRESQL")
    print("=" * 70)

    results = migrate_data(args.source_url, args.target_url, args.batch_size)

    print("\n" + "=" * 70)
    print(" MIGRATION SUMMARY REPORT")
    print("=" * 70)
    print(f"{'Table Name':<32} {'Source':<10} {'Target':<10} {'Status':<15}")
    print("-" * 70)
    total_src = 0
    total_tgt = 0
    for tbl, info in results.items():
        total_src += info["source"]
        total_tgt += info["target"]
        print(f"{tbl:<32} {info['source']:<10} {info['target']:<10} {info['status']:<15}")
    print("-" * 70)
    print(f"{'TOTAL ROWS':<32} {total_src:<10} {total_tgt:<10}")
    print("=" * 70)

if __name__ == "__main__":
    main()
