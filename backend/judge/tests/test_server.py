"""Judge service API surface."""
from fastapi.testclient import TestClient

from app.server import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_demo_queues_requested_number_of_jobs():
    with TestClient(app) as client:
        response = client.post("/demo/hello-world?count=3")
    assert response.status_code == 200
    assert len(response.json()["jobs"]) == 3


def test_demo_count_is_clamped():
    with TestClient(app) as client:
        response = client.post("/demo/hello-world?count=9000")
    assert len(response.json()["jobs"]) == 50


def test_status_stream_delivers_job_events():
    # no isolate on test hosts: jobs still flow through and finish as failed
    with TestClient(app) as client, client.websocket_connect("/ws/status") as ws:
        client.post("/demo/hello-world?count=1")
        seen = set()
        for _ in range(3):
            seen.add(ws.receive_json()["type"])
    assert "job.queued" in seen
    assert "job.started" in seen
