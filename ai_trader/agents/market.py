"""Market analyst agent: gathers market data per symbol into a context snapshot."""
from __future__ import annotations

from typing import Any

from ..data.market_data import MarketData
from .base import BaseAgent


class MarketAnalyst(BaseAgent):
    name = "market"

    def __init__(self, market: MarketData) -> None:
        super().__init__()
        self.market = market

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        timeframe = context.get("timeframe", "1h")
        limit = context.get("bars_to_fetch", 200)
        snapshot = self.market.fetch_market_snapshot(timeframe=timeframe, limit=limit)
        self.log.info("Collected market snapshot for %d symbols", len(snapshot))
        return {"market_snapshot": snapshot, "timeframe": timeframe}