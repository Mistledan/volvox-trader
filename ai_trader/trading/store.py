"""Portfolio store abstraction.

A PortfolioStore is the persistence + execution surface that the agents act on.
Two implementations exist:

- PaperBroker (``trading.broker``) - the original JSON-file store used in
  self-hosted mode (``ai-trader --run``).
- DbPortfolioStore (``api.dbstore``) - a per-user store backed by the database,
  used by the multi-user SaaS API.

Agents are typed against this protocol so one risk/execution pipeline serves
both self-hosted bots and SaaS accounts.
"""
from __future__ import annotations

from typing import Any, Protocol

from .broker import Position, Trade


class PortfolioStore(Protocol):
    """Minimal surface the agent pipeline needs from a portfolio."""

    # price feed
    def update_prices(self, prices: dict[str, float]) -> None: ...

    def last_price(self, symbol: str) -> float: ...

    # account state
    @property
    def cash(self) -> float: ...

    @property
    def initial_balance(self) -> float: ...

    @property
    def positions(self) -> dict[str, Position]: ...

    @property
    def trades(self) -> list[Trade]: ...

    def equity(self, prices: dict[str, float] | None = None) -> float: ...

    def realized_today(self) -> float: ...

    # orders
    def market_buy(
        self,
        symbol: str,
        quote_amount: float,
        price: float,
        reason: str = "",
        confidence: float = 0.0,
    ) -> Trade: ...

    def market_sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        reason: str = "",
        confidence: float = 0.0,
    ) -> Trade: ...

    # audit
    def record_decision(self, decision: dict[str, Any], status: str) -> None: ...