# Volvox Trader

An **100% fully-automated, agent-native crypto paper-trading bot** with a live dashboard.

The strategy agent (an LLM) reads live market indicators, decides a trade,
a risk agent approves or rejects it, and an execution agent fills it on a
paper broker — no human in the loop. Every decision is logged and visible
on the dashboard.

## How it works

A loop runs every `cycle_seconds` (default 300s):

1. **Market agent** — fetches live OHLCV + tickers from the first reachable
   exchange in a fallback chain (ccxt) and computes indicators
   (SMA, EMA, RSI, MACD, Bollinger, ATR).
2. **Strategy agent** — an LLM analyzes the snapshot and returns a JSON
   decision: `buy` / `sell` / `hold`, with confidence and order size.
3. **Risk agent** — enforces position limits, daily-loss halt, and a
   minimum-confidence threshold.
4. **Execution agent** — places the order on the paper broker if approved.

The default LLM runs **100% locally** on Ollama (no API key, no cost), but a
provider-agnostic LiteLLM client means OpenAI, Anthropic, Gemini, or Groq work
by changing `config/default.yaml` only.

## Features

- Multi-exchange fallback chain (works from wherever the machine has network)
- Local LLM decisions via Ollama, or any provider via LiteLLM
- Paper trading with persisted portfolio state (`logs/paper_state.json`)
- Live FastAPI dashboard: equity, cash, PnL, positions, decisions, trades
- Structured logging + 12 unit tests

## Quick start

Requirements: Python 3.12, [Ollama](https://ollama.com) (for local LLM).

```bash
python -m venv .venv
\.venv\Scripts\activate            # Windows
pip install -e .[dev]
ollama run llama3.2               # or any model; set it in config
```

Configure `config/default.yaml`:

```yaml
llm:
  provider: ollama
  model: ollama/ai-trader
```

Run the bot (paper trading by default — **no real money**):

```bash
ai-trader --once      # one decision cycle
ai-trader --run       # autonomous loop, runs forever
```

Run the dashboard:

```bash
ai-trader-dashboard   # or: python -m ai_trader.dashboard
# open http://127.0.0.1:8079
```

Run the multi-user SaaS API (auth, per-user paper portfolios, decisions, leaderboard):

```bash
ai-trader-server      # or: python -m ai_trader.server
# OpenAPI docs at http://127.0.0.1:8099/api/v1/docs
# The built web dashboard (web/dist) is served by the same process:
#   http://127.0.0.1:8099   (rebuild with: cd web && npm run build)
```

Run tests:

```bash
python -m pytest tests -q
```

## Project layout

```
ai_trader/
  agents/          # market, strategy (LLM), risk, execution
  data/            # ccxt market data + technical indicators
  llm/             # provider-agnostic LLM client (LiteLLM)
  trading/         # paper broker + portfolio state
  dashboard.py     # FastAPI live dashboard
  orchestrator.py  # the autonomous agent loop
  main.py          # CLI (--once / --run / --exchange)
config/default.yaml
```

## Safety

This is a **paper-trading** bot. It never touches real money unless `mode: live`
is configured with real exchange credentials. Use at your own risk.

## Deployment

Deploy the whole stack (bot + dashboard, $0/month) on Oracle Cloud Always Free,
or run it in Docker. See [`deploy/DEPLOY.md`](deploy/DEPLOY.md) for the full
walkthrough. Vercel/serverless is not suitable (needs a persistent host).

## Documentation

- [`docs/ROADMAP.md`](docs/ROADMAP.md) — product plan: SaaS website + mobile app + real-funds phases
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the brain, stores, and API fit together

## Roadmap

- [ ] Backtesting on historical OHLCV
- [ ] Live exchange trading (config-gated)
- [ ] HTTPS + custom domain via Caddy
- [ ] News / sentiment input for the strategy agent