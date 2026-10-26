import io
import os
import pytest
from contextlib import redirect_stdout
from alembic.config import Config
from alembic import command
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.app.database import (
    Base,
    normalize_database_url,
    mask_database_url,
)
from backend.app.models.views import POSTGRESQL_VIEWS_SQL, SQLITE_VIEWS_SQL
import backend.app.models  # Register all models


class TestPostgreSQLConfiguration:
    def test_normalize_database_url_converts_postgres_to_psycopg2(self):
        url_legacy = "postgres://app_user:secret_pwd@db.internal:5432/datanexus"
        normalized = normalize_database_url(url_legacy)
        assert normalized == "postgresql+psycopg2://app_user:secret_pwd@db.internal:5432/datanexus"

    def test_normalize_database_url_preserves_sqlite(self):
        url_sqlite = "sqlite:///./datanexus.db"
        assert normalize_database_url(url_sqlite) == "sqlite:///./datanexus.db"

    def test_normalize_database_url_handles_standard_postgresql(self):
        url_pg = "postgresql://app_user:secret_pwd@localhost:5432/datanexus"
        normalized = normalize_database_url(url_pg)
        assert normalized == "postgresql+psycopg2://app_user:secret_pwd@localhost:5432/datanexus"

    def test_mask_database_url_hides_credentials(self):
        url = "postgresql+psycopg2://datanexus_admin:super_secret_password_123@db-host.cloud:5432/production_db"
        masked = mask_database_url(url)
        assert "super_secret_password_123" not in masked
        assert "***" in masked
        assert "datanexus_admin" in masked
        assert "db-host.cloud:5432/production_db" in masked

    def test_mask_database_url_sanitizes_sqlite(self):
        url = "sqlite:///./data/datanexus.db"
        assert mask_database_url(url) == "sqlite_local"


class TestPostgreSQLSchemaCompilation:
    def test_all_models_compile_clean_postgresql_ddl(self):
        """Verify that every SQLAlchemy model cleanly generates PostgreSQL-compliant DDL."""
        pg_dialect = postgresql.dialect()
        tables = Base.metadata.sorted_tables

        assert len(tables) >= 15, f"Expected at least 15 core tables, got {len(tables)}"

        for table in tables:
            ddl_stmt = str(CreateTable(table).compile(dialect=pg_dialect)).strip()
            assert ddl_stmt.startswith("CREATE TABLE"), f"Failed generating DDL for {table.name}"
            assert table.name in ddl_stmt

    def test_data_types_for_postgresql(self):
        """Ensure invoice and analytics models compile valid PostgreSQL column types."""
        pg_dialect = postgresql.dialect()
        fact_invoice_table = Base.metadata.tables["fact_invoice"]
        ddl = str(CreateTable(fact_invoice_table).compile(dialect=pg_dialect))

        assert "invoice_number VARCHAR" in ddl
        assert "total_amount FLOAT" in ddl
        assert "TIMESTAMP WITHOUT TIME ZONE" in ddl
        assert "SERIAL" in ddl or "INTEGER" in ddl


class TestDialectAwareViews:
    def test_postgresql_views_contain_expected_definitions(self):
        expected_views = [
            "v_daily_ingestion",
            "v_processing_performance",
            "v_invoice_spend_by_vendor",
            "v_overdue_invoices",
            "v_data_quality_scorecard",
            "v_pipeline_freshness",
            "v_indexing_coverage",
        ]
        assert len(POSTGRESQL_VIEWS_SQL) == 7

        for view_name in expected_views:
            matched = any(view_name in sql for sql in POSTGRESQL_VIEWS_SQL)
            assert matched, f"View {view_name} missing in POSTGRESQL_VIEWS_SQL"

    def test_postgresql_views_use_create_or_replace(self):
        for sql in POSTGRESQL_VIEWS_SQL:
            assert "CREATE OR REPLACE VIEW" in sql

    def test_sqlite_views_use_create_view_if_not_exists(self):
        for sql in SQLITE_VIEWS_SQL:
            assert "CREATE VIEW IF NOT EXISTS" in sql


class TestAlembicMigrations:
    def test_alembic_offline_sql_generation_for_postgresql(self, monkeypatch):
        """Test that Alembic can compile offline SQL migrations targeting PostgreSQL without error."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/datanexus")

        cfg = Config("alembic.ini")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            command.upgrade(cfg, "head", sql=True)

        generated_sql = buffer.getvalue()
        assert len(generated_sql) > 5000
        assert "CREATE TABLE alembic_version" in generated_sql
        assert "CREATE TABLE documents" in generated_sql
        assert "CREATE TABLE fact_invoice" in generated_sql
        assert "CREATE TABLE lineage_edges" in generated_sql
