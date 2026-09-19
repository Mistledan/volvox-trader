"""Single-cycle engine backed by a PortfolioStore and shared agents.

This drives one autonomous decision cycle for any account (self-hosted JSON
broker or SaaS database store), reusing the standard agent pipeline.
"""
from __future__ import annotations

from typing import Any

from ..agents.execution import ExecutionAgent
from ..agents.risk import RiskAgent
from ..agents.strategy import StrategyAgent
from ..config import Config
from ..data.market_data import MarketData
from ..llm.client import LLMClient
from ..trading.store import PortfolioStore
from ..utils.logging import get_logger

log = get_logger("ai_trader.engine")


def portfolio_summary(store: PortfolioStore, prices: dict[str, float]) -> dict[str, Any]:
    positions: dict[str, dict[str, Any]] = {}
    for sym, pos in store.positions.items():
        px = prices.get(sym, pos.avg_price)
        positions[sym] = {
            "symbol": sym,
            "quantity": pos.quantity,
            "avg_price": pos.avg_price,
            "value_usd": round(pos.quantity * px, 2),
        }
    equity = store.equity(prices)
    return {
        "cash_usd": round(store.cash, 2),
        "equity_usd": round(equity, 2),
        "unrealized_pnl_usd": round(equity - store.initial_balance, 2),
        "open_positions": positions,
        "recent_trades": [
            {"side": t.side, "symbol": t.symbol, "qty": t.quantity, "price": t.price, "pnl": t.pnl_usd, "at": t.timestamp}
            for t in store.trades[:10]
        ],
    }


def run_cycle(
    store: PortfolioStore,
    market: MarketData,
    llm: LLMClient | Any,
    cfg: Config,
) -> dict[str, Any]:
    """Run one full autonomous cycle against `store`; persist all outcomes."""
    prices: dict[str, float] = {}
    for symbol in cfg.symbols:
        try:
            prices[symbol] = market.fetch_ticker(symbol)["last"]
        except Exception as exc:  # noqa: BLE001 - keep going with snapshot data
            log.warning("ticker fetch failed for %s: %s", symbol, exc)
    store.update_prices(prices)

    snapshot = market.fetch_market_snapshot(timeframe=cfg.timeframe, limit=cfg.bars_to_fetch)
    context: dict[str, Any] = {
        "prices": prices,
        "market_snapshot": snapshot,
        "portfolio": portfolio_summary(store, prices),
    }

    context.update(StrategyAgent(llm).run(context))
    context.update(RiskAgent(cfg.risk, store).run(context))
    context.update(ExecutionAgent(store).run(context))

    decision = context.get("decision", {})
    status = context.get("status", "noop")
    store.record_decision(decision, status)
    return context