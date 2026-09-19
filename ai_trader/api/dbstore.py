"""Database-backed portfolio store: one paper portfolio per SaaS account."""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Account, DecisionRecord, Holding, TradeRecord, session_scope
from ..trading.broker import Position, Trade
from ..trading.store import PortfolioStore


class DbPortfolioStore:
    """Implements the PortfolioStore surface on top of the accounts tables."""

    def __init__(self, account: Account) -> None:
        self._account_id = account.id
        self._init_balance = account.initial_balance
        self._prices: dict[str, float] = {}

    # ---- price feed ---------------------------------------------------
    def update_prices(self, prices: dict[str, float]) -> None:
        self._prices.update(prices)

    def last_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 0.0)

    # ---- account state ------------------------------------------------
    @property
    def cash(self) -> float:
        with session_scope() as s:
            acc = s.get(Account, self._account_id)
            return float(acc.cash_usd) if acc else 0.0

    @property
    def initial_balance(self) -> float:
        return self._init_balance

    @property
    def positions(self) -> dict[str, Position]:
        with session_scope() as s:
            rows = s.scalars(select(Holding).where(Holding.account_id == self._account_id)).all()
            return {
                r.symbol: Position(
                    symbol=r.symbol, quantity=r.quantity, avg_price=r.avg_price, opened_at=r.opened_at
                )
                for r in rows
                if r.quantity > 1e-12
            }

    @property
    def trades(self) -> list[Trade]:
        with session_scope() as s:
            rows = (
                s.scalars(
                    select(TradeRecord)
                    .where(TradeRecord.account_id == self._account_id)
                    .order_by(TradeRecord.timestamp.desc())
                    .limit(500)
                )
                .all()
            )
            return [self._to_trade(r) for r in rows]

    def equity(self, prices: dict[str, float] | None = None) -> float:
        prices = prices or self._prices
        with session_scope() as s:
            acc = s.get(Account, self._account_id)
            if acc is None:
                return 0.0
            total = float(acc.cash_usd)
            for row in s.scalars(select(Holding).where(Holding.account_id == self._account_id)).all():
                px = prices.get(row.symbol, row.avg_price)
                total += row.quantity * px
            return total

    @staticmethod
    def day_key() -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def realized_today(self) -> float:
        today = self.day_key()
        start_today = time.mktime(time.strptime(today, "%Y-%m-%d"))
        with session_scope() as s:
            rows = s.scalars(
                select(TradeRecord).where(
                    TradeRecord.account_id == self._account_id,
                    TradeRecord.side == "sell",
                    TradeRecord.timestamp >= start_today,
                )
            ).all()
            return float(sum(r.pnl_usd for r in rows))

    # ---- orders -------------------------------------------------------
    def market_buy(
        self,
        symbol: str,
        quote_amount: float,
        price: float,
        reason: str = "",
        confidence: float = 0.0,
    ) -> Trade:
        if quote_amount <= 0:
            raise ValueError("quote_amount must be positive")
        with session_scope() as s:
            acc = s.get(Account, self._account_id)
            if acc is None:
                raise ValueError("account not found")
            if quote_amount > acc.cash_usd:
                quote_amount = float(acc.cash_usd)
            if quote_amount <= 0:
                raise ValueError("insufficient cash")
            qty = quote_amount / price
            holding = s.scalar(select(Holding).where(Holding.account_id == self._account_id, Holding.symbol == symbol))
            if holding is None:
                holding = Holding(account_id=self._account_id, symbol=symbol, quantity=0.0, avg_price=0.0)
                s.add(holding)
                s.flush()
            new_qty = holding.quantity + qty
            holding.avg_price = ((holding.avg_price * holding.quantity) + quote_amount) / new_qty
            holding.quantity = new_qty
            holding.opened_at = time.time()
            acc.cash_usd = float(acc.cash_usd) - quote_amount
            trade = Trade(
                symbol=symbol, side="buy", quantity=qty, price=price, value_usd=quote_amount,
                pnl_usd=0.0, reasoning=reason, confidence=confidence, timestamp=time.time(),
            )
            s.add(
                TradeRecord(
                    account_id=self._account_id, symbol=symbol, side="buy", quantity=qty, price=price,
                    value_usd=quote_amount, pnl_usd=0.0, reasoning=reason, confidence=confidence,
                    timestamp=trade.timestamp,
                )
            )
            return trade

    def market_sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        reason: str = "",
        confidence: float = 0.0,
    ) -> Trade:
        with session_scope() as s:
            acc = s.get(Account, self._account_id)
            if acc is None:
                raise ValueError("account not found")
            holding = s.scalar(select(Holding).where(Holding.account_id == self._account_id, Holding.symbol == symbol))
            if holding is None:
                raise ValueError(f"no position in {symbol}")
            qty = min(quantity, holding.quantity)
            if qty <= 0:
                raise ValueError("quantity must be positive")
            proceeds = qty * price
            cost = qty * holding.avg_price
            pnl = proceeds - cost
            holding.quantity -= qty
            if holding.quantity <= 1e-12:
                s.delete(holding)
            acc.cash_usd = float(acc.cash_usd) + proceeds
            trade = Trade(
                symbol=symbol, side="sell", quantity=qty, price=price, value_usd=proceeds,
                pnl_usd=pnl, reasoning=reason, confidence=confidence, timestamp=time.time(),
            )
            s.add(
                TradeRecord(
                    account_id=self._account_id, symbol=symbol, side="sell", quantity=qty, price=price,
                    value_usd=proceeds, pnl_usd=pnl, reasoning=reason, confidence=confidence,
                    timestamp=trade.timestamp,
                )
            )
            return trade

    # ---- audit --------------------------------------------------------
    def record_decision(self, decision: dict[str, Any], status: str = "noop") -> None:
        with session_scope() as s:
            s.add(
                DecisionRecord(
                    account_id=self._account_id,
                    action=str(decision.get("action", "hold")),
                    symbol=str(decision.get("symbol", "none")),
                    confidence=float(decision.get("confidence", 0.0)),
                    size=float(decision.get("order_size_usd", 0.0)),
                    reasoning=str(decision.get("reasoning", ""))[:1000],
                    status=status,
                )
            )

    # ---- helpers ------------------------------------------------------
    @staticmethod
    def _to_trade(r: TradeRecord) -> Trade:
        return Trade(
            symbol=r.symbol, side=r.side, quantity=r.quantity, price=r.price, value_usd=r.value_usd,
            pnl_usd=r.pnl_usd, reasoning=r.reasoning, confidence=r.confidence, timestamp=r.timestamp,
        )

    def decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        with session_scope() as s:
            rows = (
                s.scalars(
                    select(DecisionRecord)
                    .where(DecisionRecord.account_id == self._account_id)
                    .order_by(DecisionRecord.timestamp.desc())
                    .limit(limit)
                )
                .all()
            )
            return [
                {
                    "action": r.action,
                    "symbol": r.symbol,
                    "confidence": r.confidence,
                    "size": r.size,
                    "reasoning": r.reasoning,
                    "status": r.status,
                    "timestamp": r.timestamp,
                }
                for r in rows
            ]


Session = Session  # re-export for typing convenience