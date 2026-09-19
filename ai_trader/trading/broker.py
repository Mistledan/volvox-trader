"""In-memory + persisted portfolio state for paper trading."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    opened_at: float


@dataclass
class Trade:
    symbol: str
    side: str  # buy | sell
    quantity: float
    price: float
    value_usd: float
    pnl_usd: float
    reasoning: str
    confidence: float
    timestamp: float


@dataclass
class Portfolio:
    initial_balance: float
    cash_usd: float = field(default=0.0)
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    last_pnl_per_day: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.cash_usd:
            self.cash_usd = self.initial_balance


class PaperBroker:
    """Simulates a spot exchange: positions, fills at last price, PnL tracking."""

    def __init__(self, initial_balance: float, data_file: str | Path | None = None) -> None:
        self.portfolio = Portfolio(initial_balance=initial_balance)
        self.data_file = Path(data_file) if data_file else None
        self._prices: dict[str, float] = {}
        self.decisions: list[dict[str, Any]] = []
        if self.data_file and self.data_file.exists():
            self._load()

    # ---- price feeding -------------------------------------------------
    def update_prices(self, prices: dict[str, float]) -> None:
        self._prices.update(prices)

    def last_price(self, symbol: str) -> float:
        return self._prices.get(symbol, 0.0)

    # ---- account -------------------------------------------------------
    @property
    def cash(self) -> float:
        return self.portfolio.cash_usd

    @property
    def initial_balance(self) -> float:
        return self.portfolio.initial_balance

    @property
    def positions(self) -> dict[str, Position]:
        return self.portfolio.positions

    @property
    def trades(self) -> list[Trade]:
        return self.portfolio.trades

    def equity(self, prices: dict[str, float] | None = None) -> float:
        prices = prices or self._prices
        loc = self.portfolio.cash_usd
        for sym, pos in self.portfolio.positions.items():
            loc += pos.quantity * prices.get(sym, pos.avg_price)
        return loc

    def day_key(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    # ---- orders --------------------------------------------------------
    def market_buy(self, symbol: str, quote_amount: float, price: float, reason: str = "", confidence: float = 0.0) -> Trade:
        if quote_amount <= 0:
            raise ValueError("quote_amount must be positive")
        if quote_amount > self.portfolio.cash_usd:
            quote_amount = self.portfolio.cash_usd
        if quote_amount <= 0:
            raise ValueError("insufficient cash")
        qty = quote_amount / price
        pos = self.portfolio.positions.get(symbol)
        new_qty = (pos.quantity if pos else 0.0) + qty
        new_avg = ((pos.avg_price * pos.quantity if pos else 0.0) + quote_amount) / new_qty
        self.portfolio.positions[symbol] = Position(
            symbol=symbol, quantity=new_qty, avg_price=new_avg, opened_at=time.time()
        )
        self.portfolio.cash_usd -= quote_amount
        trade = Trade(
            symbol=symbol, side="buy", quantity=qty, price=price,
            value_usd=quote_amount, pnl_usd=0.0, reasoning=reason,
            confidence=confidence, timestamp=time.time(),
        )
        self.portfolio.trades.append(trade)
        self._save()
        return trade

    def market_sell(self, symbol: str, quantity: float, price: float, reason: str = "", confidence: float = 0.0) -> Trade:
        pos = self.portfolio.positions.get(symbol)
        if pos is None:
            raise ValueError(f"no position in {symbol}")
        quantity = min(quantity, pos.quantity)
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        proceeds = quantity * price
        cost = quantity * pos.avg_price
        pnl = proceeds - cost
        self.portfolio.cash_usd += proceeds
        if pos.quantity - quantity <= 1e-12:
            del self.portfolio.positions[symbol]
        else:
            pos.quantity -= quantity
        trade = Trade(
            symbol=symbol, side="sell", quantity=quantity, price=price,
            value_usd=proceeds, pnl_usd=pnl, reasoning=reason,
            confidence=confidence, timestamp=time.time(),
        )
        self.portfolio.trades.append(trade)
        key = self.day_key()
        self.portfolio.last_pnl_per_day[key] = self.portfolio.last_pnl_per_day.get(key, 0.0) + pnl
        self._save()
        return trade

    def realized_today(self) -> float:
        return self.portfolio.last_pnl_per_day.get(self.day_key(), 0.0)

    def record_decision(self, decision: dict[str, Any], status: str = "noop") -> None:
        self.decisions.append({"decision": decision, "status": status, "timestamp": time.time()})

    # ---- persistence ---------------------------------------------------
    def _state(self) -> dict[str, Any]:
        return {
            "initial_balance": self.portfolio.initial_balance,
            "cash_usd": self.portfolio.cash_usd,
            "positions": {s: asdict(p) for s, p in self.portfolio.positions.items()},
            "trades": [asdict(t) for t in self.portfolio.trades],
            "last_pnl_per_day": self.portfolio.last_pnl_per_day,
        }

    def _load(self) -> None:
        try:
            state = json.loads(self.data_file.read_text(encoding="utf-8"))
            self.portfolio.cash_usd = state.get("cash_usd", self.portfolio.cash_usd)
            self.portfolio.positions = {
                s: Position(**p) for s, p in state.get("positions", {}).items()
            }
            self.portfolio.trades = [Trade(**t) for t in state.get("trades", [])]
            self.portfolio.last_pnl_per_day = state.get("last_pnl_per_day", {})
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    def _save(self) -> None:
        if self.data_file is None:
            return
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            self.data_file.write_text(json.dumps(self._state(), indent=2), encoding="utf-8")
        except OSError:
            pass