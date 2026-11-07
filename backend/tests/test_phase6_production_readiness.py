import asyncio
import json
import os
import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from backend.app.main import app
from backend.app.models.document import Document
from backend.app.services.streaming import PipelineEventBroadcaster, event_broadcaster

client = TestClient(app)

class TestPipelineEventBroadcasterAndStreaming:
    """Validate in-memory asynchronous pub/sub broadcaster and Server-Sent Events."""

    def test_broadcaster_subscribe_and_broadcast(self):
        async def _run():
            broadcaster = PipelineEventBroadcaster()
            channel = "test_channel"
            queue = await broadcaster.subscribe(channel)

            test_data = {"message": "stage_1_done", "code": 200}
            await broadcaster.broadcast("stage_event", test_data, channel)

            assert not queue.empty()
            event = await queue.get()
            assert event["event"] == "stage_event"
            assert event["data"] == test_data
            assert "timestamp" in event

            await broadcaster.unsubscribe(channel, queue)
            assert channel not in broadcaster._subscribers

        asyncio.run(_run())

    def test_stream_events_formatting_and_snapshot(self):
        async def _run():
            broadcaster = PipelineEventBroadcaster()
            channel = "doc:stream_test"
            initial_history = [
                {"stage": "text_extraction", "status": "completed", "duration_ms": 120}
            ]

            gen = broadcaster.stream_events(channel=channel, initial_events=initial_history)
            
            # First yielded item should be the initial snapshot
            first_chunk = await anext(gen)
            assert first_chunk.startswith("event: snapshot\n")
            assert "text_extraction" in first_chunk

            # Clean up
            await gen.aclose()

        asyncio.run(_run())

    def test_document_events_stream_endpoint(self, db_session: Session):
        doc = db_session.query(Document).filter(Document.status == "completed").first()
        if not doc:
            pytest.skip("No completed document available in database for stream test.")

        # Test request against SSE stream endpoint using streaming context
        with client.stream("GET", f"/api/documents/{doc.id}/events/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            assert response.headers.get("x-accel-buffering") == "no"
            
            # Read first chunk (snapshot)
            for chunk in response.iter_lines():
                if chunk:
                    assert "event:" in chunk or "data:" in chunk or "snapshot" in chunk
                    break

    def test_global_pipeline_events_stream_endpoint(self):
        with client.stream("GET", "/api/documents/events/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

class TestPowerBiMQueriesAndDirectQueryScript:
    """Validate Power BI M-query generation, Kimball star schema code, and script export."""

    def test_get_powerbi_m_queries_endpoint(self):
        response = client.get("/api/analytics/powerbi/m-queries")
        assert response.status_code == 200
        data = response.json()

        assert "database_engine" in data
        assert "is_directquery_supported" in data
        assert "star_schema_tables" in data
        assert "curated_views" in data
        assert "dax_measures_script" in data
        assert "complete_m_script" in data

        # Check all 6 star schema tables
        expected_tables = ["dim_vendor", "dim_date", "dim_document", "fact_invoice", "fact_invoice_line", "fact_pipeline_run"]
        for tbl in expected_tables:
            assert tbl in data["star_schema_tables"]
            table_info = data["star_schema_tables"][tbl]
            assert "m_query" in table_info
            assert table_info["m_query"].startswith("let\n")
            assert table_info["m_query"].strip().endswith("in\n    TargetTable") or table_info["m_query"].strip().endswith("in\n    Source")

        # Check curated views
        assert len(data["curated_views"]) >= 7
        assert "v_invoice_spend_by_vendor" in data["curated_views"]
        assert "v_overdue_invoices" in data["curated_views"]
        assert "v_data_quality_scorecard" in data["curated_views"]

        # Check DAX measures
        assert "Total Invoiced Spend USD =" in data["dax_measures_script"]
        assert "Overdue Liability Exposure =" in data["dax_measures_script"]
        assert "Data Quality Pass Rate % =" in data["dax_measures_script"]

    def test_export_powerbi_script_endpoint(self):
        response = client.get("/api/analytics/powerbi/export-script")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "attachment; filename=datanexus_powerbi_" in response.headers.get("content-disposition", "")
        
        script_text = response.text
        assert "DataNexus Power Query (M) Automation Script" in script_text
        assert "Curated DAX Measure Definitions" in script_text
        assert "fact_invoice" in script_text

class TestProductionDeploymentConfiguration:
    """Validate production deployment artifacts: Docker Compose, Dockerfiles, and Nginx reverse proxy."""

    def test_docker_compose_syntax_and_topology(self):
        compose_path = os.path.join(os.path.dirname(__file__), "..", "..", "docker-compose.yml")
        assert os.path.exists(compose_path), "docker-compose.yml must exist"

        with open(compose_path, "r", encoding="utf-8") as f:
            compose_cfg = yaml.safe_load(f)

        services = compose_cfg.get("services", {})
        assert "postgres" in services, "Must declare postgres service"
        assert "elasticsearch" in services, "Must declare elasticsearch service"
        assert "backend" in services, "Must declare backend service"
        assert "frontend" in services, "Must declare frontend service"

        # Verify PostgreSQL configuration
        pg = services["postgres"]
        assert pg["image"].startswith("postgres:16")
        assert "healthcheck" in pg
        assert "5432:5432" in pg["ports"]

        # Verify Elasticsearch configuration
        es = services["elasticsearch"]
        assert "elasticsearch" in es["image"]
        assert "healthcheck" in es
        assert "9200:9200" in es["ports"]

        # Verify Backend dependency on healthy services
        backend = services["backend"]
        assert "depends_on" in backend
        assert "postgres" in backend["depends_on"]
        assert backend["depends_on"]["postgres"]["condition"] == "service_healthy"

    def test_dockerfile_backend_configuration(self):
        df_path = os.path.join(os.path.dirname(__file__), "..", "..", "Dockerfile.backend")
        assert os.path.exists(df_path), "Dockerfile.backend must exist"

        with open(df_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "FROM python:3.13" in content
        assert "HEALTHCHECK" in content
        assert "8008" in content
        assert "docker-entrypoint.sh" in content

    def test_nginx_and_frontend_configuration(self):
        nginx_path = os.path.join(os.path.dirname(__file__), "..", "..", "nginx.conf")
        assert os.path.exists(nginx_path), "nginx.conf must exist"

        with open(nginx_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify SSE streaming headers in reverse proxy
        assert "proxy_buffering off;" in content
        assert "proxy_pass http://backend:8008/api/;" in content
        assert "gzip on;" in content
