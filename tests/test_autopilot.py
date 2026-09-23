"""Tests for autopilot scheduling, copy trading, token expiry, and rate limits."""
import os
import time

os.environ["AI_TRADER_FAKE_LLM"] = "1"
import importlib
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ai_trader.api.ratelimit import RateLimiter


def _fresh_db() -> str:
    return f"sqlite:///{tempfile.mkdtemp()}/autopilot.sqlite3"


class FakeMarket:
    def fetch_ticker(self, symbol):
        return {"last": 50000.0}

    def fetch_market_snapshot(self, timeframe="1h", limit=200):
        return {"BTC/USDT": {"features": {"rsi_14": 55.0, "sma_20": 100.0}, "ticker": {"last": 50000.0}}}


def _register(client, username):
    r = client.post("/api/v1/auth/register", json={"username": username, "password": "secret123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", _fresh_db())
    monkeypatch.setenv("AI_TRADER_FAKE_LLM", "1")
    # Reload only the server module (it init_db()s against the fresh URL and
    # re-binds db imports). Reloading ai_trader.db would re-register mappers
    # and corrupt later test files in the same process.
    import importlib

    from ai_trader import server as server_module

    server = importlib.reload(server_module)
    monkeypatch.setattr(server, "get_market", lambda: FakeMarket())
    client = TestClient(server.app)
    return {"server": server, "client": client}


def test_autopilot_toggle_and_leaderboard(ctx):
    client = ctx["client"]
    h = _register(client, "alice")
    r = client.get("/api/v1/me", headers=h)
    assert r.json()["autopilot"] is False
    assert r.json()["leader_username"] is None

    r = client.post("/api/v1/me/autopilot", json={"enabled": True}, headers=h)
    assert r.status_code == 200
    assert r.json()["autopilot"] is True

    r = client.get("/api/v1/me", headers=h)
    assert r.json()["autopilot"] is True

    lb = client.get("/api/v1/leaderboard").json()["users"]
    assert lb[0]["username"] == "alice"
    assert lb[0]["autopilot"] is True

    client.post("/api/v1/me/autopilot", json={"enabled": False}, headers=h)
    assert client.get("/api/v1/me", headers=h).json()["autopilot"] is False


def test_copy_leader_validation(ctx):
    client = ctx["client"]
    _register(client, "bob")
    h_bob = _register(client, "carol")

    r = client.post("/api/v1/me/copy", json={"leader_username": "bob"}, headers=h_bob)
    assert r.status_code == 200
    assert r.json()["leader_username"] == "bob"

    r = client.post("/api/v1/me/copy", json={"leader_username": "ghost"}, headers=h_bob)
    assert r.status_code == 404

    r = client.post("/api/v1/me/copy", json={"leader_username": "carol"}, headers=h_bob)
    assert r.status_code == 400  # cannot copy yourself


def test_token_expiry_rejected(ctx):
    client = ctx["client"]
    h = _register(client, "dave")
    token = h["Authorization"].split(" ")[1]
    from ai_trader.auth import token_hash
    from ai_trader.db import ApiToken, session_scope

    with session_scope() as s:
        tok = s.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash(token)))
        tok.expires_at = time.time() - 10
    assert client.get("/api/v1/me", headers=h).status_code == 401


def test_refresh_issues_new_token(ctx):
    client = ctx["client"]
    h = _register(client, "erin")
    r = client.post("/api/v1/auth/refresh", headers=h)
    assert r.status_code == 200
    fresh = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/v1/me", headers=fresh).json()["username"] == "erin"


def test_cycle_halted_on_daily_loss(ctx):
    from ai_trader.api.dbstore import DbPortfolioStore
    from ai_trader.db import Account, session_scope

    client = ctx["client"]
    h = _register(client, "frank")
    with session_scope() as s:
        acc = s.scalar(select(Account))
    store = DbPortfolioStore(acc)
    store.update_prices({"BTC/USDT": 50000.0})
    store.market_buy("BTC/USDT", 2000.0, 50000.0, reason="seed", confidence=0.9)
    store.market_sell("BTC/USDT", 0.04, 30000.0, reason="crash", confidence=0.9)

    r = client.post("/api/v1/me/cycle", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "halted"
    assert body["risk_ok"] is False

    p = client.get("/api/v1/me/portfolio", headers=h).json()
    assert p["daily_loss_halted"] is True


def test_autopilot_round_and_equity_history(ctx):
    client = ctx["client"]
    h = _register(client, "grace")
    client.post("/api/v1/me/autopilot", json={"enabled": True}, headers=h)

    client.get("/api/v1/me/portfolio", headers=h)  # records a snapshot
    eq = client.get("/api/v1/me/equity", headers=h)
    assert eq.status_code == 200
    assert len(eq.json()["points"]) >= 1

    server = ctx["server"]
    from ai_trader.api.autopilot import run_autopilot_round

    res = run_autopilot_round(server.cfg, lambda: FakeMarket(), server.make_llm)
    assert len(res["accounts"]) == 1
    me = client.get("/api/v1/me", headers=h).json()
    assert me["last_cycle_at"] is not None
    assert len(client.get("/api/v1/me/equity", headers=h).json()["points"]) >= 2


def test_copy_mirrors_leader_positions(ctx):
    from ai_trader.api.dbstore import DbPortfolioStore
    from ai_trader.api.autopilot import run_autopilot_round
    from ai_trader.db import Account, session_scope

    client = ctx["client"]
    h_lead = _register(client, "lead")
    h_fol = _register(client, "follower")
    client.post("/api/v1/me/copy", json={"leader_username": "lead"}, headers=h_fol)
    client.post("/api/v1/me/autopilot", json={"enabled": True}, headers=h_lead)
    client.post("/api/v1/me/autopilot", json={"enabled": True}, headers=h_fol)

    with session_scope() as s:
        lead = s.scalar(select(Account).join(Account.user).where(Account.user.has(username="lead")))
        store = DbPortfolioStore(lead)
        store.update_prices({"BTC/USDT": 50000.0})
        store.market_buy("BTC/USDT", 5000.0, 50000.0, reason="leader buy", confidence=0.9)

    server = ctx["server"]
    run_autopilot_round(server.cfg, lambda: FakeMarket(), server.make_llm)

    with session_scope() as s:
        fol = s.scalar(select(Account).join(Account.user).where(Account.user.has(username="follower")))
        fol_store = DbPortfolioStore(fol)
        pos = fol_store.positions
    assert "BTC/USDT" in pos
    assert pos["BTC/USDT"].quantity == pytest.approx(0.1, rel=0.01)


def test_rate_limiter_window():
    limiter = RateLimiter(limit=3, window_s=60.0)
    assert limiter.check("b", "ip")
    assert limiter.check("b", "ip")
    assert limiter.check("b", "ip")
    assert not limiter.check("b", "ip")
    assert limiter.check("b", "other-ip")