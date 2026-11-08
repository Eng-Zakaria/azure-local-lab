"""Integration tests against the running lab. Run with:

docker compose --profile streaming up -d
uv run pytest -m integration
"""

import json
import time
import uuid

import pytest

from cloudkit import Settings, blob_service, eventhub_consumer, eventhub_producer, postgres_connect

pytestmark = pytest.mark.integration


def test_blob_roundtrip():
    svc = blob_service(Settings.from_env())
    container = svc.get_container_client(f"it-{uuid.uuid4().hex[:8]}")
    container.create_container()
    try:
        container.upload_blob("bronze/hello.json", json.dumps({"ok": True}))
        body = container.download_blob("bronze/hello.json").readall()
        assert json.loads(body) == {"ok": True}
    finally:
        container.delete_container()


def test_pgvector_similarity():
    with postgres_connect() as conn, conn.cursor() as cur:
        cur.execute("CREATE TEMP TABLE docs (id int, emb vector(3))")
        cur.execute("INSERT INTO docs VALUES (1,'[1,0,0]'),(2,'[0,1,0]'),(3,'[0.9,0.1,0]')")
        cur.execute("SELECT id FROM docs ORDER BY emb <=> '[1,0,0]' LIMIT 2")
        assert [r[0] for r in cur.fetchall()] == [1, 3]


def test_eventhubs_send_and_receive():
    from azure.eventhub import EventData

    marker = uuid.uuid4().hex
    with eventhub_producer("telemetry") as producer:
        batch = producer.create_batch()
        batch.add(EventData(json.dumps({"marker": marker})))
        producer.send_batch(batch)

    seen: list[str] = []
    consumer = eventhub_consumer("telemetry", consumer_group="lab")

    def on_event(partition_context, event):
        if event is not None and marker in event.body_as_str():
            seen.append(marker)
            consumer.close()

    deadline = time.time() + 30
    with consumer:
        consumer.receive(on_event=on_event, starting_position="-1", max_wait_time=5)
        while not seen and time.time() < deadline:
            time.sleep(0.5)
    assert seen == [marker]
