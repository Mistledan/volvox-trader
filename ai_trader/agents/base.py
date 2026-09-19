"""Base agent interface shared by all AI-Trader agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..utils.logging import get_logger


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.log = get_logger(f"ai_trader.agent.{self.name}")

    @abstractmethod
    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute one step. Returns a result dict describing its output."""