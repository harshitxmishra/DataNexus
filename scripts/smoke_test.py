#!/usr/bin/env python
"""
DataNexus Platform Smoke Test & Health Verification.
Performs an end-to-end check of active backend endpoints and database records.
"""
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "http://127.0.0.1:8008"

def test_endpoint(name: str, path: str, expected_status: int = 200) -> dict:
    url = f"{BASE_URL}{path}"
    print(f"Testing {name.ljust(35)} -> {path} ... ", end="")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DataNexus-SmokeTest/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
            data = json.loads(response.read().decode("utf-8"))
            if status == expected_status:
                print(f"[OK] ({status})")
                return data
            else:
                print(f"[FAIL] Expected {expected_status}, got {status}")
                return {}
    except urllib.error.HTTPError as e:
        print(f"[FAIL] HTTP {e.code}: {e.reason}")
        return {}
    except Exception as e:
        print(f"[ERROR] {e}")
        return {}

def main():
    print("=" * 65)
    print(" DataNexus Platform — End-to-End Smoke Test")
    print("=" * 65)

    failures = 0

    # 1. Health Checks
    live = test_endpoint("Liveness Probe", "/api/health/liveness")
    if not live or live.get("status") != "alive":
        failures += 1

    ready = test_endpoint("Readiness Probe", "/api/health/readiness")
    if not ready or ready.get("database", {}).get("status") != "healthy":
        failures += 1

    # 2. Documents
    docs = test_endpoint("Documents Library", "/api/documents")
    if not docs or len(docs) == 0:
        print("  Warning: No documents found in database. Run 'python scripts/seed_database.py'")
    else:
        first_id = docs[0]['id']
        print(f"  Found {len(docs)} seeded document(s). First ID: {first_id}")
        coords = test_endpoint("PDF Evidence Coordinates", f"/api/documents/{first_id}/evidence-coordinates")
        if not coords or not coords.get("is_pdf"):
            failures += 1

    # 3. Analytics & Overview
    overview = test_endpoint("Analytics Overview", "/api/analytics/overview")
    if not overview or overview.get("total_documents", 0) == 0:
        failures += 1

    perf = test_endpoint("Processing Performance", "/api/analytics/processing-performance")
    if not perf:
        failures += 1

    spend = test_endpoint("Vendor Spend Analytics", "/api/analytics/vendor-spend")
    if not spend:
        failures += 1

    # 4. Phase 5 Data Platform, Lineage & BI Endpoints
    scorecard = test_endpoint("Data Quality Scorecard", "/api/data-platform/quality/scorecard")
    if not scorecard or scorecard.get("total_evaluations", 0) == 0:
        failures += 1

    views = test_endpoint("Curated Analytical Views", "/api/analytics/views")
    if not views or len(views.get("views", [])) < 7:
        failures += 1

    pbi = test_endpoint("Power BI Semantic Model", "/api/analytics/powerbi/semantic-model")
    if not pbi or len(pbi.get("tables", [])) < 6:
        failures += 1

    mqueries = test_endpoint("Power BI M-Queries Generator", "/api/analytics/powerbi/m-queries")
    if not mqueries or len(mqueries.get("star_schema_tables", {})) < 6:
        failures += 1

    lineage = test_endpoint("Lineage Summary", "/api/lineage/summary")
    if not lineage or lineage.get("total_nodes", 0) == 0:
        failures += 1

    # 5. Search & QA
    # Test POST search query
    print(f"Testing {'Hybrid Search Query'.ljust(35)} -> /api/search/query ... ", end="")
    try:
        search_payload = json.dumps({"query": "cloud infrastructure", "mode": "hybrid", "top_k": 3}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/search/query",
            data=search_payload,
            headers={"Content-Type": "application/json", "User-Agent": "DataNexus-SmokeTest/1.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            s_data = json.loads(resp.read().decode("utf-8"))
            if resp.status == 200 and len(s_data.get("results", [])) > 0:
                print(f"[OK] (Found {len(s_data['results'])} hits)")
            else:
                print(f"[WARN] Returned 0 search hits")
    except Exception as e:
        print(f"[ERROR] {e}")
        failures += 1

    print("=" * 65)
    if failures == 0:
        print(" [PASS] All critical smoke tests verified successfully.")
        sys.exit(0)
    else:
        print(f" [FAIL] {failures} check(s) failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
