"""CLI entrypoint for AI-Trader."""
from __future__ import annotations

import argparse

from .config import PROJECT_ROOT, load_config
from .orchestrator import AIOrchestrator
from .utils.logging import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(prog="ai-trader", description="AI-Trader: 100% Fully-Automated Agent-Native Trading")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "default.yaml"), help="path to YAML config")
    parser.add_argument("--exchange", default=None, help="force a specific ccxt exchange id")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit")
    parser.add_argument("--run", action="store_true", help="run the autonomous loop forever")
    args = parser.parse_args()

    cfg = load_config(args.config)
    setup_logging(cfg.logging.level, cfg.log_file_path)
    orch = AIOrchestrator(cfg, exchange_id=args.exchange)

    if args.once:
        orch.cycle()
    else:
        orch.run_forever()


if __name__ == "__main__":
    main()