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


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode()


def _judge_payload(**overrides) -> dict:
    payload = {
        "source": "int main(){}",
        "language": "cpp",
        "checker": "// testlib checker",
        "tests": [{"index": 1, "input": _b64(b"1 2\n"), "answer": _b64(b"3\n")}],
    }
    payload.update(overrides)
    return payload


def test_judge_requires_at_least_one_test():
    with TestClient(app) as client:
        response = client.post("/judge", json=_judge_payload(tests=[]))
    assert response.status_code == 422


def test_judge_returns_a_verdict_shape():
    # no isolate on CI hosts, so the verdict is XX; the contract still holds
    with TestClient(app) as client:
        response = client.post("/judge", json=_judge_payload())
    body = response.json()
    assert response.status_code == 200
    assert set(body) >= {"run_id", "verdict", "score", "tests", "compile_log"}


def test_judge_emits_events_on_the_status_stream():
    with TestClient(app) as client, client.websocket_connect("/ws/status") as ws:
        client.post("/judge", json=_judge_payload())
        kinds = {ws.receive_json()["type"] for _ in range(2)}
    assert "judge.started" in kinds
