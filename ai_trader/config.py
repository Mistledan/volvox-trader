"""Configuration loading for AI-Trader."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 1024


@dataclass
class RiskConfig:
    max_position_pct: float = 0.20
    max_daily_loss_pct: float = 0.05
    min_confidence: float = 0.60
    order_size_pct: float = 0.10
    max_open_positions: int = 5


@dataclass
class PaperConfig:
    initial_balance_usd: float = 10000.0
    max_history_minutes: int = 60
    data_file: str = "logs/paper_state.json"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/ai-trader.log"


@dataclass
class ExchangeConfig:
    id: str = "binance"
    sandbox: bool = False
    attempts: int = 1  # reserved


@dataclass
class Config:
    mode: str = "paper"
    exchanges: list[ExchangeConfig] = field(default_factory=lambda: [ExchangeConfig()])
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)  # active one, overridden by CLI
    symbols: list[str] = field(default_factory=lambda: ["BTC/USDT"])
    timeframe: str = "1h"
    cycle_seconds: int = 300
    bars_to_fetch: int = 200
    llm: LLMConfig = field(default_factory=LLMConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    paper: PaperConfig = field(default_factory=PaperConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @property
    def data_file_path(self) -> Path:
        p = Path(self.paper.data_file)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p

    @property
    def log_file_path(self) -> Path:
        p = Path(self.logging.file)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p


def load_config(path: str | Path | None = None) -> Config:
    """Load config from a YAML file, falling back to defaults."""
    load_dotenv(PROJECT_ROOT / ".env")
    cfg = Config()
    if path is None:
        default = PROJECT_ROOT / "config" / "default.yaml"
        path = default if default.exists() else None
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        cfg = _apply(raw)
    return cfg


def _apply(raw: dict) -> Config:
    cfg = Config()
    cfg.mode = raw.get("mode", cfg.mode)
    cfg.symbols = raw.get("symbols", cfg.symbols)
    cfg.timeframe = raw.get("timeframe", cfg.timeframe)
    cfg.cycle_seconds = raw.get("cycle_seconds", cfg.cycle_seconds)
    cfg.bars_to_fetch = raw.get("bars_to_fetch", cfg.bars_to_fetch)

    ex = raw.get("exchange") or {}
    cfg.exchange = ExchangeConfig(id=ex.get("id", cfg.exchange.id), sandbox=ex.get("sandbox", cfg.exchange.sandbox))
    exs = raw.get("exchanges")
    if exs is None:
        # if only `exchange` is given, build one-entry fallback list
        cfg.exchanges = [cfg.exchange]
    else:
        cfg.exchanges = [ExchangeConfig(id=e.get("id", "binance"), sandbox=e.get("sandbox", False)) for e in exs]

    llm = raw.get("llm") or {}
    cfg.llm = LLMConfig(
        provider=llm.get("provider", cfg.llm.provider),
        model=llm.get("model", cfg.llm.model),
        temperature=llm.get("temperature", cfg.llm.temperature),
        max_tokens=llm.get("max_tokens", cfg.llm.max_tokens),
    )

    rk = raw.get("risk") or {}
    cfg.risk = RiskConfig(
        max_position_pct=rk.get("max_position_pct", cfg.risk.max_position_pct),
        max_daily_loss_pct=rk.get("max_daily_loss_pct", cfg.risk.max_daily_loss_pct),
        min_confidence=rk.get("min_confidence", cfg.risk.min_confidence),
        order_size_pct=rk.get("order_size_pct", cfg.risk.order_size_pct),
        max_open_positions=rk.get("max_open_positions", cfg.risk.max_open_positions),
    )

    pp = raw.get("paper") or {}
    cfg.paper = PaperConfig(
        initial_balance_usd=pp.get("initial_balance_usd", cfg.paper.initial_balance_usd),
        max_history_minutes=pp.get("max_history_minutes", cfg.paper.max_history_minutes),
        data_file=pp.get("data_file", cfg.paper.data_file),
    )

    lg = raw.get("logging") or {}
    cfg.logging = LoggingConfig(level=lg.get("level", cfg.logging.level), file=lg.get("file", cfg.logging.file))

    cfg.exchange.sandbox = bool(os.getenv("EXCHANGE_SANDBOX", cfg.exchange.sandbox))
    return cfg