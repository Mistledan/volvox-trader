"""Execution agent: converts a risky-approved decision into a broker order."""
from __future__ import annotations

from typing import Any

from ..trading.store import PortfolioStore
from .base import BaseAgent


class ExecutionAgent(BaseAgent):
    name = "execution"

    def __init__(self, broker: PortfolioStore) -> None:
        super().__init__()
        self.broker = broker

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        decision = context.get("decision", {})
        prices = context.get("prices", {})
        action = decision.get("action", "hold")
        symbol = decision.get("symbol", "none")
        reason = decision.get("reasoning", "")
        confidence = float(decision.get("confidence", 0.0))

        if action not in ("buy", "sell"):
            return {"trade": None, "status": "noop"}

        price = prices.get(symbol, 0.0)
        if price <= 0:
            self.log.warning("No price for %s; skipping", symbol)
            return {"trade": None, "status": "no_price", "symbol": symbol}

        try:
            if action == "buy":
                size = float(decision.get("order_size_usd") or 0.0)
                if size <= 0:
                    return {"trade": None, "status": "zero_order"}
                trade = self.broker.market_buy(symbol, size, price, reason=reason, confidence=confidence)
                status = "filled"
            else:
                pos = self.broker.positions.get(symbol)
                if pos is None:
                    return {"trade": None, "status": "no_position", "symbol": symbol}
                fraction = float(decision.get("order_size_usd") or 1.0)
                fraction = max(0.0, min(1.0, fraction))
                qty = pos.quantity * fraction
                if qty <= 0:
                    return {"trade": None, "status": "zero_quantity", "symbol": symbol}
                trade = self.broker.market_sell(symbol, qty, price, reason=reason, confidence=confidence)
                status = "filled"
        except (ValueError, RuntimeError) as exc:
            self.log.warning("Fill failed: %s", exc)
            return {"trade": None, "status": "error", "error": str(exc)}

        self.log.info("FILLED %s %s qty=%.6f price=%.2f", action.upper(), symbol, trade.quantity, trade.price)
        return {"trade": trade, "status": status}