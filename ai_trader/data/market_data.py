"""Market data fetching via ccxt (exchange-agnostic, multi-exchange fallback)."""
from __future__ import annotations

import os
import time
from typing import Callable, TypeVar

import ccxt
import pandas as pd

from ..config import ExchangeConfig
from ..utils.logging import get_logger
from . import indicators

log = get_logger("ai_trader.data.market")

T = TypeVar("T")


def _retry(what: str, fn: Callable[[], T], attempts: int = 3, base_delay: float = 1.0) -> T:
    """Call `fn` with exponential backoff so transient network blips don't kill a cycle."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last = exc
            if i < attempts - 1:
                delay = base_delay * (2**i)
                log.warning(
                    "%s attempt %d/%d failed (%s); retrying in %.1fs",
                    what, i + 1, attempts, exc, delay,
                )
                time.sleep(delay)
    raise MarketDataError(f"{what} failed after {attempts} attempts: {last}") from last


class MarketDataError(RuntimeError):
    pass


class MarketData:
    """Fetches OHLCV + tickers from a chain of ccxt exchanges.

    Tries each configured exchange in order and keeps the first one that
    resolves and loads markets (e.g. binance -> gateio -> huobi -> mexc),
    so it works wherever the machine has network reachability.
    """

    def __init__(self, exchange_cfgs: list[ExchangeConfig]) -> None:
        self._ex = None
        self._exchange_id = None
        self.symbols: list[str] = []
        last_err: Exception | None = None
        for cfg in exchange_cfgs:
            try:
                optioned = self._instantiate(cfg.id, cfg.sandbox)
                # single connectivity probe per candidate; the real market
                # layer retries heavier (load_markets / fetch_*) afterwards.
                _retry(f"Exchange {cfg.id} probe", optioned.load_markets, attempts=1)
                self._ex = optioned
                self._exchange_id = cfg.id
                break
            except Exception as exc:  # noqa: BLE001 - fall through to next exchange
                last_err = exc
                log.warning("Exchange %s unavailable: %s", cfg.id, exc)
        if self._ex is None:
            raise MarketDataError(f"No reachable exchange from candidates "
                                  f"{[c.id for c in exchange_cfgs]}; last error: {last_err}")

    @staticmethod
    def _instantiate(exchange_id: str, sandbox: bool):
        klass = getattr(ccxt, exchange_id)
        if klass is None:
            raise MarketDataError(f"Unknown ccxt exchange id: {exchange_id!r}")
        ex = klass(
            {
                "enableRateLimit": True,
                "timeout": int(os.getenv("MARKET_TIMEOUT_MS", "5000")),
                "connectTimeout": int(os.getenv("MARKET_CONNECT_TIMEOUT_MS", "3000")),
            }
        )
        ex.set_sandbox_mode(sandbox)
        return ex

    def load_markets(self, symbols: list[str]) -> None:
        markets = _retry("load_markets", self._ex.load_markets, attempts=2)
        missing = [s for s in symbols if s not in markets]
        if missing:
            log.warning("Symbols not found on %s: %s", self._exchange_id, missing)
        self.symbols = list(symbols)

    @property
    def exchange_id(self) -> str:
        return self._exchange_id or "?"

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
    ) -> pd.DataFrame:
        """Fetch OHLCV and return an augmented DataFrame with indicators."""
        try:
            raw = _retry(
                f"fetch_ohlcv {symbol}",
                lambda: self._ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit),
            )
        except MarketDataError as exc:
            raise MarketDataError(f"fetch_ohlcv failed for {symbol} on {self.exchange_id}: {exc}") from exc
        if not raw:
            raise MarketDataError(f"No OHLCV returned for {symbol}")
        df = indicators.to_frame(raw)
        return indicators.compute_features(df)

    def fetch_ticker(self, symbol: str, attempts: int = 2) -> dict:
        try:
            ticker = _retry(f"fetch_ticker {symbol}", lambda: self._ex.fetch_ticker(symbol), attempts=attempts, base_delay=0.25)
        except MarketDataError as exc:
            raise MarketDataError(f"fetch_ticker failed for {symbol}: {exc}") from exc
        return {
            "symbol": symbol,
            "last": float(ticker.get("last") or 0.0),
            "bid": float(ticker.get("bid") or 0.0),
            "ask": float(ticker.get("ask") or 0.0),
            "high_24h": float(ticker.get("high") or 0.0),
            "low_24h": float(ticker.get("low") or 0.0),
            "change_pct_24h": float(ticker.get("percentage") or 0.0),
        }

    def fetch_market_snapshot(self, timeframe: str = "1h", limit: int = 200) -> dict[str, dict]:
        """Fetch every configured symbol and return `{symbol: {features, ticker}}`."""
        snapshot: dict[str, dict] = {}
        for symbol in self.symbols:
            try:
                df = self.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                feats = indicators.latest_features(df)
                ticker = self.fetch_ticker(symbol)
                snapshot[symbol] = {"features": feats, "ticker": ticker}
            except MarketDataError as exc:
                log.warning("Skipping %s: %s", symbol, exc)
        if not snapshot:
            raise MarketDataError("No market data could be fetched for any symbol")
        return snapshot