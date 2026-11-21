"""
DataNexus v2.0.0 — OpenTelemetry Distributed Tracing.

Instruments FastAPI, the 7-stage ingestion pipeline, and the RAG pipeline
with spans. Supports:
  - OTLP export in production (OTEL_EXPORTER_OTLP_ENDPOINT)
  - JSON/in-memory span collector in benchmark mode
  - Noop when OTEL_ENABLED=false
"""

import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Global tracer reference
_tracer = None
_span_exporter = None
_provider = None


def setup_telemetry(app=None):
    """
    Initialize OpenTelemetry tracing based on config.
    Call once during app lifespan startup.
    """
    global _tracer, _span_exporter, _provider

    if not getattr(settings, "OTEL_ENABLED", False):
        logger.info("OpenTelemetry disabled (OTEL_ENABLED=false)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import (
            SimpleSpanProcessor,
            BatchSpanProcessor,
        )

        service_name = getattr(settings, "OTEL_SERVICE_NAME", "datanexus")
        resource = Resource.create({"service.name": service_name})
        _provider = TracerProvider(resource=resource)

        otlp_endpoint = getattr(settings, "OTEL_EXPORTER_OTLP_ENDPOINT", "")

        if otlp_endpoint:
            # Production: OTLP gRPC exporter
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                _provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"OTel OTLP exporter configured: {otlp_endpoint}")
            except ImportError:
                logger.warning(
                    "opentelemetry-exporter-otlp not installed, falling back to in-memory"
                )
                _setup_inmemory_exporter(_provider)
        else:
            # Benchmark/dev: in-memory span collector
            _setup_inmemory_exporter(_provider)

        trace.set_tracer_provider(_provider)
        _tracer = trace.get_tracer("datanexus", "2.0.0")

        # Instrument FastAPI if app provided
        if app:
            try:
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

                FastAPIInstrumentor.instrument_app(app)
                logger.info("FastAPI instrumented with OpenTelemetry")
            except ImportError:
                logger.info(
                    "opentelemetry-instrumentation-fastapi not installed, skipping"
                )

        logger.info("OpenTelemetry tracing initialized")

    except ImportError:
        logger.warning("OpenTelemetry SDK not installed — tracing disabled")
    except Exception as e:
        logger.warning(f"OpenTelemetry setup failed: {e}")


class InMemorySpanCollector:
    """Thread-safe in-memory span collector for benchmark latency profiling."""

    def __init__(self):
        self._spans = []

    def export(self, spans):
        self._spans.extend(spans)
        try:
            from opentelemetry.sdk.trace.export import SpanExportResult
            return SpanExportResult.SUCCESS
        except Exception:
            return None

    def get_finished_spans(self):
        return list(self._spans)

    def clear(self):
        self._spans.clear()

    def shutdown(self):
        pass


def _setup_inmemory_exporter(provider):
    """Configure in-memory span exporter for benchmarks."""
    global _span_exporter
    try:
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        _span_exporter = InMemorySpanCollector()
        provider.add_span_processor(SimpleSpanProcessor(_span_exporter))
        logger.info("OTel in-memory span exporter configured (benchmark mode)")
    except Exception as e:
        logger.warning(f"In-memory span exporter setup failed: {e}")


def get_tracer():
    """Get the configured tracer, or a noop tracer if OTel is disabled."""
    global _tracer
    if _tracer:
        return _tracer
    try:
        from opentelemetry import trace

        return trace.get_tracer("datanexus", "2.0.0")
    except ImportError:
        return _NoopTracer()


def get_collected_spans():
    """
    Retrieve all collected spans from the in-memory exporter.
    Returns list of span data dicts for benchmark metric computation.
    """
    global _span_exporter
    if _span_exporter is None:
        return []
    try:
        spans = _span_exporter.get_finished_spans()
        return [
            {
                "name": s.name,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration_ns": (s.end_time - s.start_time) if s.end_time and s.start_time else 0,
                "duration_ms": round(
                    (s.end_time - s.start_time) / 1_000_000, 2
                )
                if s.end_time and s.start_time
                else 0,
                "attributes": dict(s.attributes) if s.attributes else {},
                "status": str(s.status.status_code) if s.status else "UNSET",
            }
            for s in spans
        ]
    except Exception:
        return []


def clear_collected_spans():
    """Clear in-memory span buffer."""
    global _span_exporter
    if _span_exporter:
        try:
            _span_exporter.clear()
        except Exception:
            pass


@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    record_exception: bool = True,
):
    """
    Context manager for creating an OTel span.
    Gracefully noops if OTel is not configured.
    
    Usage:
        with trace_span("pipeline.chunking", {"document_id": doc_id}):
            do_work()
    """
    tracer = get_tracer()
    try:
        span = tracer.start_span(name)
        if attributes:
            for k, v in attributes.items():
                try:
                    span.set_attribute(k, v)
                except Exception:
                    pass
        try:
            yield span
        except Exception as e:
            if record_exception:
                try:
                    span.record_exception(e)
                    from opentelemetry.trace import StatusCode

                    span.set_status(StatusCode.ERROR, str(e))
                except Exception:
                    pass
            raise
        finally:
            try:
                span.end()
            except Exception:
                pass
    except Exception:
        # If even creating the span fails, yield None
        yield None


class _NoopSpan:
    def set_attribute(self, key, value):
        pass

    def record_exception(self, exc):
        pass

    def set_status(self, *a, **kw):
        pass

    def end(self):
        pass


class _NoopTracer:
    def start_span(self, name, **kw):
        return _NoopSpan()

    def start_as_current_span(self, name, **kw):
        @contextmanager
        def _ctx():
            yield _NoopSpan()

        return _ctx()
