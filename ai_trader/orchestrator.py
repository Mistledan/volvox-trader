"""AI-Trader orchestrator: drives the fully-automated agent loop."""
from __future__ import annotations

import time
from typing import Any

from .agents.execution import ExecutionAgent
from .agents.market import MarketAnalyst
from .agents.risk import RiskAgent
from .agents.strategy import StrategyAgent
from .config import Config, ExchangeConfig
from .data.market_data import MarketData
from .llm.client import LLMClient
from .trading.broker import PaperBroker
from .utils.logging import get_logger

log = get_logger("ai_trader.orchestrator")


class AIOrchestrator:
    """Runs one full agent cycle per call; external loop controls cadence."""

    def __init__(self, cfg: Config, exchange_id: str | None = None) -> None:
        self.cfg = cfg
        self.exchange_id = exchange_id
        self.market = MarketData(self._exchange_chain(cfg, exchange_id))
        self.market.load_markets(cfg.symbols)
        self.broker = PaperBroker(cfg.paper.initial_balance_usd, cfg.data_file_path)
        self.llm = LLMClient(cfg.llm)

        self.market_agent = MarketAnalyst(self.market)
        self.strategy_agent = StrategyAgent(self.llm)
        self.risk_agent = RiskAgent(cfg.risk, self.broker)
        self.execution_agent = ExecutionAgent(self.broker)

    @staticmethod
    def _exchange_chain(cfg: Config, exchange_id: str | None) -> list[ExchangeConfig]:
        if exchange_id:
            return [ExchangeConfig(id=exchange_id, sandbox=False)]
        return cfg.exchanges

    def cycle(self) -> dict[str, Any]:
        """Execute one full autonomous trading cycle."""
        prices = self._current_prices() or {}
        self.broker.update_prices(prices)

        context: dict[str, Any] = {
            "timeframe": self.cfg.timeframe,
            "bars_to_fetch": self.cfg.bars_to_fetch,
            "portfolio": self._portfolio_summary(prices),
            "prices": prices,
        }

        # 1) Market analyst gathers the data
        context.update(self.market_agent.run(context))

        # 2) LLM strategy agent decides
        context.update(self.strategy_agent.run(context))

        # 3) Risk agent approves / rejects
        context.update(self.risk_agent.run(context))

        # 4) Execution agent places the order if approved
        context.update(self.execution_agent.run(context))

        return context

    def run_forever(self) -> None:
        """Run the agent loop until interrupted (Ctrl+C)."""
        log.info("AI-Trader fully-automated loop starting (cycle=%ds)", self.cfg.cycle_seconds)
        try:
            while True:
                started = time.monotonic()
                try:
                    result = self.cycle()
                    self._log_cycle(result)
                except Exception as exc:  # noqa: BLE001 - keep the loop alive
                    log.exception("Cycle failed: %s", exc)
                elapsed = time.monotonic() - started
                remaining = self.cfg.cycle_seconds - elapsed
                if remaining > 0:
                    time.sleep(remaining)
        except KeyboardInterrupt:
            log.info("Shutting down AI-Trader.")
            self._summary()

    def _log_cycle(self, result: dict[str, Any]) -> None:
        trade = result.get("trade")
        if trade is not None:
            log.info("--- CYCLE RESULT: %s %s %s | PnL %.2f", trade.side.upper(), trade.symbol, trade.quantity, trade.pnl_usd)
        else:
            log.info("--- CYCLE RESULT: %s | status=%s", result.get("decision", {}).get("action", "?"), result.get("status", "noop"))
        log.info("Equity: $%.2f | Cash: $%.2f | Positions: %d", self.broker.equity(), self.broker.portfolio.cash_usd, len(self.broker.portfolio.positions))

    def _summary(self) -> None:
        log.info("Total trades: %d", len(self.broker.portfolio.trades))

    # ---- helpers -----------------------------------------------------
    def _current_prices(self) -> dict[str, float]:
        prices: dict[str, float] = {}
        for symbol in self.cfg.symbols:
            try:
                prices[symbol] = self.market.fetch_ticker(symbol)["last"]
            except Exception as exc:  # noqa: BLE001
                log.warning("Ticker fetch failed for %s: %s", symbol, exc)
        return prices

    def _portfolio_summary(self, prices: dict[str, float] | None = None) -> dict[str, Any]:
        prices = prices or {}
        equity = self.broker.equity(prices)
        positions = {}
        for sym, pos in self.broker.portfolio.positions.items():
            px = prices.get(sym, pos.avg_price)
            positions[sym] = {"quantity": pos.quantity, "avg_price": pos.avg_price, "value_usd": pos.quantity * px}
        return {
            "cash_usd": round(self.broker.portfolio.cash_usd, 2),
            "equity_usd": round(equity, 2),
            "unrealized_pnl_usd": round(equity - self.broker.portfolio.initial_balance, 2),
            "open_positions": positions,
            "recent_trades": [
                {"side": t.side, "symbol": t.symbol, "qty": t.quantity, "price": t.price, "pnl": t.pnl_usd, "at": t.timestamp}
                for t in self.broker.portfolio.trades[-10:]
            ],
        }