# Architecture

Volvox Trader is built in two layers that share one brain:

```
                ┌──────────────────────────────────────────────┐
                │            THE BRAIN (agent pipeline)        │
                │   Market → Strategy(LLM) → Risk → Execution  │
                └──────────────┬───────────────────────────────┘
                               │  acts on a PortfolioStore
                ┌──────────────┴───────────────────────────────┐
                │           PortfolioStore (protocol)          │
                ├───────────────────────────┬──────────────────┤
                │ PaperBroker (JSON file)   │ DbPortfolioStore  │
                │  self-hosted --run mode   │  SaaS accounts    │
                └───────────────────────────┴──────────────────┘
                                             bonus: LiveExchangeStore
                                             (ccxt + user keys, future)
```

## The brain
`ai_trader/api/engine.py:run_cycle()` runs one decision cycle against *any*
`PortfolioStore`:

1. **Market** — fetches OHLCV + tickers through the ccxt exchange fallback chain
   and computes indicators (SMA/EMA/RSI/MACD/Bollinger/ATR) → `market_snapshot`.
2. **Strategy** — the LLM (LiteLLM; default local Ollama) returns a JSON
   decision `{action, symbol, confidence, order_size_usd, reasoning}`.
3. **Risk** — enforces limits: position size ≤ 20% equity, order ≤ 10% equity,
   daily-loss halt at 5%, confidence floor 0.60, max 5 open positions.
4. **Execution** — fills approved orders on the store and records the trade.

Every decision is written back to the store (`record_decision`) so the full
decision history is auditable.

## Portfolio stores
Both implement `ai_trader/trading/store.py:PortfolioStore`:

- **PaperBroker** — original JSON-file state. Used by `ai-trader --run`
  (self-host) and the local dashboard.
- **DbPortfolioStore** — per-account database store. Used by the SaaS API.
  Each network/DB operation is its own short transaction.

Adding real trading later = a third implementation of the same protocol driven
by ccxt with the user's encrypted exchange credentials.

## SaaS API (`ai_trader/server.py`, port 8099)
- FastAPI + SQLAlchemy. Auth via opaque bearer tokens (PBKDF2 passwords, SHA-256
  token hashes).
- Routes: auth, `/me/*` portfolio/trades/decisions/cycle, public `/leaderboard`,
  `/health`. CORS open for the future web + mobile clients.
- OpenAPI at `/api/v1/docs`.

## Database (default SQLite → Postgres in prod)
| Table | Purpose |
|---|---|
| `users`, `api_tokens` | auth |
| `accounts` | one paper portfolio per user |
| `holdings` | open positions |
| `trade_records`, `decision_records` | full audit trail |

`DATABASE_URL=postgresql+psycopg2://...` flips an unchanged codebase to
Postgres.

## Processes you can run
```
ai-trader --run              # self-hosted bot loop (JSON broker, Ollama LLM)
ai-trader-dashboard          # local dashboard @ :8079
ai-trader-server             # SaaS API @ :8099 (multi-user, DB)
```

## Deployment
Deploy everything (currently just the self-host bot) per `deploy/DEPLOY.md`.
For the SaaS phase: postgres service + `ai-trader-server` bound publicly behind
Caddy (HTTPS) + the web frontend (Phase 3).

## Extending
- New indicator → `ai_trader/data/indicators.py`
- New LLM → set `llm.provider/model` in `config/*.yaml`
- New risk rule → `ai_trader/agents/risk.py`
- Real trading → new `PortfolioStore` implementation (see Phase 5)