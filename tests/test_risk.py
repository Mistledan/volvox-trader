"""Tests for the risk agent."""
import pytest

from ai_trader.agents.risk import RiskAgent
from ai_trader.config import RiskConfig
from ai_trader.trading.broker import PaperBroker

DEFAULT = dict(max_position_pct=0.2, max_daily_loss_pct=0.05, min_confidence=0.6, order_size_pct=0.1, max_open_positions=5)


@pytest.fixture
def agent() -> RiskAgent:
    return RiskAgent(RiskConfig(**DEFAULT), PaperBroker(initial_balance=10000.0))


def _ctx(decision: dict, prices: dict | None = None) -> dict:
    return {"decision": decision, "prices": prices or {"BTC/USDT": 50000.0}}


def test_hold_always_ok(agent: RiskAgent) -> None:
    checks, ok = agent._evaluate({"action": "hold", "confidence": 0.0, "symbol": "none"}, {"BTC/USDT": 50000.0}, 10000.0)
    assert ok
    assert checks == []


def test_low_confidence_rejected(agent: RiskAgent) -> None:
    d = {"action": "buy", "symbol": "BTC/USDT", "confidence": 0.3, "order_size_usd": 500.0}
    checks, ok = agent._evaluate(d, {"BTC/USDT": 50000.0}, 10000.0)
    assert not ok
    assert any("confidence" in c for c in checks)


def test_oversized_order_rejected(agent: RiskAgent) -> None:
    d = {"action": "buy", "symbol": "BTC/USDT", "confidence": 0.9, "order_size_usd": 9000.0}
    checks, ok = agent._evaluate(d, {"BTC/USDT": 50000.0}, 10000.0)
    assert not ok
    assert any("too large" in c for c in checks)


def test_position_cap(agent: RiskAgent) -> None:
    agent.broker.update_prices({"BTC/USDT": 50000.0})
    for sym in ("BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT"):
        agent.broker.market_buy(sym, 1500.0, price=1.0)
    d = {"action": "buy", "symbol": "BNB/USDT", "confidence": 0.9, "order_size_usd": 5000.0}
    checks, ok = agent._evaluate(d, {"BNB/USDT": 500.0, "BTC/USDT": 50000.0}, 10000.0)
    assert not ok
    assert any("max open positions" in c for c in checks)