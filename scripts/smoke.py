"""End-to-end smoke test: one traced "pipeline run" across every running lab service.

    uv run python scripts/smoke.py

Each step is wrapped in an OpenTelemetry span, so the run shows up in Grafana
(http://localhost:3001 -> Explore -> Tempo -> service "lab-smoke").
Steps whose service is not running are reported as SKIP, not failures.
"""

from __future__ import annotations

import json
import socket
import sys
import uuid
from collections.abc import Callable

from opentelemetry import trace

from cloudkit import (
    Settings,
    blob_service,
    eventhub_producer,
    postgres_connect,
    servicebus_client,
    telemetry,
)

S = Settings.from_env()


def port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex((S.host, port)) == 0


def step_blob() -> str:
    c = blob_service(S).get_container_client("bronze")
    if not c.exists():
        c.create_container()
    name = f"smoke/{uuid.uuid4().hex}.json"
    c.upload_blob(name, json.dumps({"source": "smoke"}))
    return f"wrote bronze/{name}"


def step_pg() -> str:
    with postgres_connect(S) as conn, conn.cursor() as cur:
        cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
        row = cur.fetchone()
    return f"pgvector {row[0] if row else 'MISSING'}"


def step_eventhubs() -> str:
    from azure.eventhub import EventData

    with eventhub_producer("transactions", S) as p:
        batch = p.create_batch()
        batch.add(EventData(json.dumps({"txn": uuid.uuid4().hex, "amount": 42.0})))
        p.send_batch(batch)
    return "sent 1 event to transactions"


def step_servicebus() -> str:
    from azure.servicebus import ServiceBusMessage

    with servicebus_client(S) as sb, sb.get_queue_sender("alerts") as sender:
        sender.send_messages(ServiceBusMessage("smoke alert"))
    return "queued 1 alert"


STEPS: list[tuple[str, int, Callable[[], str]]] = [
    ("blob (Azurite)", S.blob_port, step_blob),
    ("postgres+pgvector", S.pg_port, step_pg),
    ("event hubs", S.eventhubs_port, step_eventhubs),
    ("service bus", S.servicebus_port, step_servicebus),
]


def main() -> int:
    telemetry.configure("lab-smoke", S)
    tracer = trace.get_tracer("lab-smoke")
    failures = 0
    with tracer.start_as_current_span("smoke-run"):
        for label, port, fn in STEPS:
            if S.is_local and not port_open(port):
                print(f"SKIP  {label:<20} (port {port} closed)")
                continue
            with tracer.start_as_current_span(label) as span:
                try:
                    print(f"OK    {label:<20} {fn()}")
                # report and continue: a smoke test should show the full picture
                except Exception as exc:
                    failures += 1
                    span.record_exception(exc)
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                    print(f"FAIL  {label:<20} {type(exc).__name__}: {exc}")
    telemetry.shutdown()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
