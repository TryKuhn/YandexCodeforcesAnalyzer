from fastapi.testclient import TestClient

from backend.app.server import app

client = TestClient(app)