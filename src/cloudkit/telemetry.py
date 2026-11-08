"""OpenTelemetry setup: OTLP to the local Grafana LGTM stack, or Azure Monitor / App Insights.

Instrument once with the vendor-neutral OTel API; the exporter is the only thing that changes.
"""

from __future__ import annotations

from opentelemetry import metrics, trace

from .config import Settings

_configured = False


def configure(service_name: str, s: Settings | None = None) -> None:
    global _configured
    if _configured:
        return
    s = s or Settings.from_env()

    if not s.is_local:
        s.require("appinsights_connection_string")
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError("install the azure extra: uv sync --extra azure") from exc
        configure_azure_monitor(
            connection_string=s.appinsights_connection_string,
            resource_attributes={"service.name": service_name},
        )
        _configured = True
        return

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": service_name, "deployment.environment": "local"})
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=s.otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(tp)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=s.otlp_endpoint, insecure=True), export_interval_millis=5000
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
    _configured = True


def shutdown() -> None:
    """Flush exporters (call at the end of short-lived jobs and scripts)."""
    for provider in (trace.get_tracer_provider(), metrics.get_meter_provider()):
        stop = getattr(provider, "shutdown", None)
        if callable(stop):
            stop()
