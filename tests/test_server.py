"""API-level tests: auth flow + account endpoints (uses FakeLLM, no network)."""
import os

os.environ["AI_TRADER_FAKE_LLM"] = "1"

import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _fresh_db() -> str:
    return f"sqlite:///{tempfile.mkdtemp()}/server.sqlite3"


@pytest.fixture
def client(monkeypatch, tmp_path):
    from ai_trader import db as db_module
    from ai_trader import server as server_module

    monkeypatch.setenv("DATABASE_URL", _fresh_db())
    monkeypatch.setenv("AI_TRADER_FAKE_LLM", "1")
    # re-init modules against the fresh DB
    import importlib

    for mod in ("ai_trader.db", "ai_trader.server"):
        importlib.reload(importlib.import_module(mod))
    server = importlib.import_module("ai_trader.server")
    return TestClient(server.app)


def test_register_login_me(client):
    r = client.post("/api/v1/auth/register", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 201
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
    assert r.json()["initial_balance_usd"] == 10000.0

    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"

    r = client.get("/api/v1/me")
    assert r.status_code == 401


def test_register_duplicate(client):
    body = {"username": "bob", "password": "secret123"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409


def test_portfolio_empty_and_cycle(client):
    r = client.post("/api/v1/auth/register", json={"username": "carol", "password": "secret123"})
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/v1/me/portfolio", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["equity_usd"] == 10000.0
    assert body["positions"] == []

    r = client.get("/api/v1/me/trades", headers=headers)
    assert r.status_code == 200
    assert r.json()["trades"] == []

    r = client.get("/api/v1/me/decisions", headers=headers)
    assert r.json()["decisions"] == []

    r = client.post("/api/v1/me/cycle", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["action"] == "hold"
    assert body["status"] == "noop"
    assert body["portfolio"]["equity_usd"] == 10000.0


def test_leaderboard_public(client):
    client.post("/api/v1/auth/register", json={"username": "dave", "password": "secret123"})
    r = client.get("/api/v1/leaderboard")
    assert r.status_code == 200
    assert len(r.json()["users"]) == 1
    assert r.json()["users"][0]["username"] == "dave"