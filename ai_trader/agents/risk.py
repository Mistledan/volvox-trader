"""Risk agent: validates strategy decisions against configured risk limits."""
from __future__ import annotations

from typing import Any

from ..config import RiskConfig
from ..trading.broker import PaperBroker
from .base import BaseAgent


class RiskAgent(BaseAgent):
    name = "risk"

    def __init__(self, cfg: RiskConfig, broker: PaperBroker) -> None:
        super().__init__()
        self.cfg = cfg
        self.broker = broker

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        decision = context.get("decision", {})
        prices = context.get("prices", {})
        equity = self.broker.equity(prices)
        checks, ok = self._evaluate(decision, prices, equity)
        if ok:
            self.log.info("risk approved: %s", decision.get("action"))
        else:
            self.log.warning("risk REJECTED: %s", "; ".join(checks))
        return {"risk_ok": ok, "risk_checks": checks, "equity": equity}

    def _evaluate(self, decision: dict[str, Any], prices: dict[str, float], equity: float) -> tuple[list[str], bool]:
        checks: list[str] = []
        ok = True
        action = decision.get("action", "hold")

        # 1) daily loss circuit breaker
        if self.broker.realized_today() < -self.cfg.max_daily_loss_pct * equity:
            checks.append("daily loss limit exceeded")
            ok = False
        if equity <= 0:
            checks.append("equity non-positive")
            ok = False

        # 2) position sizing bounds
        order_size = float(decision.get("order_size_usd") or 0.0)
        symbol = decision.get("symbol", "none")
        if action == "buy":
            max_order = self.cfg.order_size_pct * equity
            if order_size <= 0:
                order_size = max_order
            if order_size > max_order * 1.05:
                checks.append(f"order too large: {order_size:.2f} > {max_order:.2f}")
                ok = False
            if order_size > self.broker.portfolio.cash_usd:
                order_size = self.broker.portfolio.cash_usd
                checks.append("order clipped to available cash")
            decision["order_size_usd"] = order_size

        # 3) confidence floor
        if action != "hold" and decision.get("confidence", 0.0) < self.cfg.min_confidence:
            checks.append(f"confidence {decision.get('confidence')} < {self.cfg.min_confidence}")
            ok = False

        # 4) portfolio cap + max positions
        if action == "buy":
            if len(self.broker.portfolio.positions) >= self.cfg.max_open_positions:
                checks.append("max open positions reached")
                ok = False
            price = prices.get(symbol, 0.0)
            if price > 0:
                current_value = self.broker.portfolio.positions.get(symbol)
                cur = current_value.quantity * price if current_value else 0.0
                if cur + order_size > self.cfg.max_position_pct * equity:
                    checks.append("position would exceed max_position_pct")
                    ok = False

        # 5) symbol sanity
        if action != "hold" and symbol not in prices:
            checks.append(f"unknown symbol {symbol}")
            ok = False

        return checks, ok