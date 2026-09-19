"""Strategy agent: the LLM brain that decides trades from market context."""
from __future__ import annotations

import json
from typing import Any

from ..llm.client import LLMClient
from .base import BaseAgent

SYSTEM_PROMPT = """You are AI-Trader, a fully-automated agent-native crypto trading strategist.

You analyze market data and decide what to do. You output ONLY a JSON object with
exactly this schema:
{
  "action": "buy" | "sell" | "hold",
  "symbol": "<symbol with markets>",
  "confidence": <0.0 to 1.0>,     // certainty in your decision
  "order_size_usd": <number>,     // USD to spend (buy) or position fraction 0-1 (sell)
  "reasoning": "<short rationale>"
}

Rules:
- "action": "hold" means no trade. Symbol can be "none".
- Be decisive but disciplined: prefer holding if signals conflict or confidence < 0.6.
- Buy when indicators + momentum support long-side entry. Sell to realize profit or cut risk.
- order_size_usd on a buy is the USD amount to deploy (respect risk limits given to you).
- order_size_usd on a sell is a fraction 0-1 of the position to exit (1.0 = full exit).
- Never invent data. Base decisions only on the provided snapshot.
"""


class StrategyAgent(BaseAgent):
    name = "strategy"

    def __init__(self, llm: LLMClient) -> None:
        super().__init__()
        self.llm = llm

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        snapshot = context.get("market_snapshot", {})
        portfolio = context.get("portfolio", {})
        user_prompt = self._build_prompt(snapshot, portfolio)
        decision = self.llm.complete_json(SYSTEM_PROMPT, user_prompt)
        normalized = self._normalize(decision)
        self.log.info(
            "decision action=%s symbol=%s confidence=%.2f size=%s",
            normalized["action"], normalized["symbol"], normalized["confidence"], normalized["order_size_usd"],
        )
        return {"decision": normalized}

    def _build_prompt(self, snapshot: dict, portfolio: dict) -> str:
        summary = json.dumps({"market_snapshot": snapshot, "portfolio": portfolio}, indent=2, default=str)
        return f"Current market + portfolio state:\n{summary}\n\nMake your trading decision now." 

    def _normalize(self, decision: dict[str, Any]) -> dict[str, Any]:
        action = str(decision.get("action", "hold")).strip().lower()
        if action not in {"buy", "sell", "hold"}:
            action = "hold"
        try:
            confidence = max(0.0, min(1.0, float(decision.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        try:
            order_size = float(decision.get("order_size_usd") or 0.0)
        except (TypeError, ValueError):
            order_size = 0.0
        symbol = str(decision.get("symbol", "none") or "none").upper()
        return {
            "action": action,
            "symbol": symbol,
            "confidence": confidence,
            "order_size_usd": order_size,
            "reasoning": str(decision.get("reasoning", ""))[:500],
        }