"""End-to-end dry-run orchestration test with stubbed market + LLM."""
import pytest

from ai_trader.agents.execution import ExecutionAgent
from ai_trader.agents.risk import RiskAgent
from ai_trader.agents.strategy import StrategyAgent
from ai_trader.config import RiskConfig
from ai_trader.trading.broker import PaperBroker


class FakeLLM:
    def __init__(self, decision: dict) -> None:
        self._decision = decision

    def complete_json(self, system, user, **kwargs) -> dict:
        return self._decision


class FakeMarket:
    def __init__(self, snapshot: dict) -> None:
        self._snapshot = snapshot

    def fetch_market_snapshot(self, timeframe="1h", limit=200) -> dict:
        return self._snapshot


@pytest.fixture
def broker() -> PaperBroker:
    return PaperBroker(initial_balance=10000.0, data_file=None)


def _build_context(snapshot: dict, decision: dict, broker: PaperBroker, prices: dict) -> dict:
    return {
        "market_snapshot": snapshot,
        "decision": decision,
        "portfolio": {"equity_usd": broker.equity(prices), "cash_usd": broker.portfolio.cash_usd},
        "prices": prices,
    }


def test_buy_pipeline(broker: PaperBroker) -> None:
    snapshot = {
        "BTC/USDT": {"features": {"sma_20": 100.0, "rsi_14": 55.0}, "ticker": {"last": 50000.0, "change_pct_24h": 1.5}}
    }
    prices = {"BTC/USDT": 50000.0}
    decision = {"action": "buy", "symbol": "BTC/USDT", "confidence": 0.9, "order_size_usd": 1000.0, "reasoning": "momentum"}

    strategy = StrategyAgent(FakeLLM(decision))
    risk = RiskAgent(RiskConfig(), broker)
    exec_agent = ExecutionAgent(broker)

    ctx = _build_context(snapshot, decision, broker, prices)
    ctx.update(strategy.run(ctx))
    ctx.update(risk.run(ctx))
    ctx.update(exec_agent.run(ctx))

    assert ctx["risk_ok"] is True
    assert ctx["status"] == "filled"
    assert ctx["trade"].symbol == "BTC/USDT"
    assert broker.portfolio.positions["BTC/USDT"].quantity > 0
    assert broker.portfolio.cash_usd < 10000.0


def test_hold_pipeline_no_trade(broker: PaperBroker) -> None:
    snapshot = {"BTC/USDT": {"features": {}, "ticker": {"last": 50000.0, "change_pct_24h": 0.0}}}
    prices = {"BTC/USDT": 50000.0}
    decision = {"action": "hold", "symbol": "none", "confidence": 0.5, "order_size_usd": 0.0, "reasoning": "signals mixed"}

    strategy = StrategyAgent(FakeLLM(decision))
    risk = RiskAgent(RiskConfig(), broker)
    exec_agent = ExecutionAgent(broker)

    ctx = _build_context(snapshot, decision, broker, prices)
    ctx.update(strategy.run(ctx))
    ctx.update(risk.run(ctx))
    ctx.update(exec_agent.run(ctx))

    assert ctx["status"] == "noop"
    assert broker.portfolio.trades == []