#!/usr/bin/env bash
# ==============================================================================
# DataNexus v3.0: PostgreSQL Query Plan & Indexing Benchmark One-Command Runner
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SQL_FILE="$REPO_ROOT/services/ledger-service/scripts/seed_and_benchmark.sql"
DB_URL="${LEDGER_DATABASE_URL:-${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/ledger}}"

echo "=============================================================================="
echo " DataNexus v3.0 — PostgreSQL Query Plan & Indexing Benchmark"
echo " Target DB: $DB_URL"
echo " SQL Script: $SQL_FILE"
echo "=============================================================================="

if ! command -v psql &> /dev/null; then
    echo "[!] psql CLI not found in PATH."
    echo "Running Python benchmark runner fallback..."
    python "$REPO_ROOT/scripts/run_sql_benchmark.py"
    exit 0
fi

echo "[*] Executing seed and benchmark script against PostgreSQL..."
psql "$DB_URL" -f "$SQL_FILE"

echo "[+] Benchmark script executed successfully."
