"""Market data fetching via ccxt (exchange-agnostic, multi-exchange fallback)."""
from __future__ import annotations

import ccxt
import pandas as pd

from ..config import ExchangeConfig
from ..utils.logging import get_logger
from . import indicators

log = get_logger("ai_trader.data.market")


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
                optioned.load_markets()
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
        ex = klass({"enableRateLimit": True})
        ex.set_sandbox_mode(sandbox)
        return ex

    def load_markets(self, symbols: list[str]) -> None:
        markets = self._ex.load_markets()
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
            raw = self._ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except ccxt.BaseError as exc:
            raise MarketDataError(f"fetch_ohlcv failed for {symbol} on {self.exchange_id}: {exc}") from exc
        if not raw:
            raise MarketDataError(f"No OHLCV returned for {symbol}")
        df = indicators.to_frame(raw)
        return indicators.compute_features(df)

    def fetch_ticker(self, symbol: str) -> dict:
        try:
            ticker = self._ex.fetch_ticker(symbol)
        except ccxt.BaseError as exc:
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