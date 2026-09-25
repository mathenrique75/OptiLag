"""Testes — FastAPI com TestClient (sem servidor externo)."""
import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from optilag_backend.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "ts" in data


def test_stats(client):
    r = client.get("/stats")
    assert r.status_code == 200
    data = r.json()
    assert "probes" in data
    assert "sessions" in data


def test_routes_list(client):
    r = client.get("/routes")
    assert r.status_code == 200
    assert len(r.json()["routes"]) >= 1


def test_engine_invalid_action(client):
    r = client.post("/engine", json={"action": "explode"})
    assert r.status_code == 422


def test_engine_start_tick_stop(client):
    r = client.post("/engine", json={"action": "start", "route": "Madrid → São Paulo"})
    assert r.status_code == 200
    assert r.json()["state"] == "optimizing"

    r = client.post("/engine", json={"action": "tick"})
    assert r.status_code == 200
    assert r.json()["metrics"]["ping"] >= 0

    r = client.post("/engine", json={"action": "stop"})
    assert r.status_code == 200
    assert r.json()["state"] == "idle"
