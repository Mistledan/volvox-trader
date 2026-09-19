"""Tests for the DB-backed portfolio store + cycle engine (no network, no LLM)."""
import pytest

from ai_trader.api.dbstore import DbPortfolioStore
from ai_trader.api.engine import run_cycle
from ai_trader.auth import hash_password, new_token, token_hash, verify_password
from ai_trader.config import Config
from ai_trader.db import Account, User, init_db, session_scope

pytestmark = pytest.mark.usefixtures("db_session")


@pytest.fixture
def db_session(tmp_path):
    init_db(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    yield


@pytest.fixture
def account(db_session):
    with session_scope() as s:
        user = User(username="tester", password_hash=hash_password("secret123"))
        s.add(user)
        s.flush()
        acc = Account(user_id=user.id, name="paper", initial_balance=10000.0, cash_usd=10000.0)
        s.add(acc)
        s.commit()
        return Account(id=acc.id, user_id=user.id, name="paper", initial_balance=10000.0, cash_usd=10000.0)


def test_auth_roundtrip():
    stored = hash_password("hunter22")
    assert verify_password("hunter22", stored)
    assert not verify_password("wrong", stored)
    token = new_token()
    assert token_hash(token) == token_hash(token)
    assert token_hash(token) != token_hash("other")


def test_db_store_buy_sell_persist(account):
    prices = {"BTC/USDT": 50000.0}
    store = DbPortfolioStore(account)
    store.update_prices(prices)
    assert store.cash == 10000.0

    t = store.market_buy("BTC/USDT", 2000.0, 50000.0, reason="buy", confidence=0.9)
    assert t.side == "buy" and t.quantity == 0.04

    store2 = DbPortfolioStore(account)  # fresh instance reads same DB
    assert store2.cash == 8000.0
    assert store2.positions["BTC/USDT"].quantity == 0.04
    assert store2.equity() == 10000.0
    assert len(store2.trades) == 1

    store2.update_prices({"BTC/USDT": 60000.0})
    assert round(store2.equity(), 2) == 10400.0

    sell = store2.market_sell("BTC/USDT", 0.02, 60000.0, reason="profit", confidence=0.8)
    assert sell.pnl_usd == 200.0
    assert store2.positions["BTC/USDT"].quantity == 0.02
    assert store2.realized_today() == 200.0


def test_db_store_record_decision(account):
    store = DbPortfolioStore(account)
    store.record_decision({"action": "hold", "symbol": "none", "confidence": 0.5, "order_size_usd": 0.0, "reasoning": "x"}, "noop")
    decisions = store.decisions()
    assert len(decisions) == 1
    assert decisions[0]["action"] == "hold"


class FakeLLM:
    def complete_json(self, system, user, **kwargs):
        return {"action": "buy", "symbol": "BTC/USDT", "confidence": 0.9, "order_size_usd": 1000.0, "reasoning": "stub"}


class FakeMarket:
    def fetch_ticker(self, symbol):
        return {"last": 50000.0}

    def fetch_market_snapshot(self, timeframe="1h", limit=200):
        return {"BTC/USDT": {"features": {"rsi_14": 55.0, "sma_20": 100.0}, "ticker": {"last": 50000.0}}}


def test_run_cycle_fills_trade(account):
    store = DbPortfolioStore(account)
    cfg = Config()
    result = run_cycle(store, FakeMarket(), FakeLLM(), cfg)
    assert result["risk_ok"] is True
    assert result["status"] == "filled"
    assert result["trade"].symbol == "BTC/USDT"
    assert store.positions["BTC/USDT"].quantity > 0
    assert store.decisions()[-1]["status"] == "filled"