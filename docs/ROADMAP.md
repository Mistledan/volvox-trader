# Volvox Trader — Product Roadmap

Turning the paper-trading bot into a real AI trading website + mobile app.

## Phase 1 — Self-hosted bot ✅ done
- Agent-native paper bot (`ai-trader --run`), live dashboard (`ai-trader-dashboard` @ :8079)
- Local LLM via Ollama, multi-exchange fallback, 20 tests passing
- Public repo + README + deploy package for Oracle Cloud / Docker (`deploy/`)

## Phase 2 — Multi-user SaaS backend ✅ done
- Database: users, tokens, accounts, holdings, trades, decisions (SQLite default → Postgres via `DATABASE_URL`)
- Auth: register / login / bearer tokens (PBKDF2, stdlib)
- API on `:8099`: portfolio, trades, decisions, run-cycle, leaderboard, health
- Per-user paper portfolios via `DbPortfolioStore`; same agent pipeline drives every account
- `ai-trader-server` entrypoint

## Phase 3 — Web SaaS frontend (website)
- Next.js/React web app consuming `/api/v1`
- Public **landing page** (how it works, live performance ticker, leaderboard)
- User **sign up / log in**, personal dashboard: equity curve, positions, decision feed, trades
- Production hosting: Postgres + FastAPI server + Next.js on the free-tier VM, Caddy for HTTPS + custom domain

## Phase 4 — Mobile app
- **React Native (Expo)** or **Flutter** — decide based on team comfort
- iOS + Android: log in, watch portfolio, decisions, push notifications on fills
- Talks to the same `/api/v1` (that is why the API is mobile-first from the start)

## Phase 5 — Real-funds trading (opt-in, later)
- `LiveExchangeStore` implementing the same `PortfolioStore` protocol with ccxt
- Users connect their own exchange API keys (encrypted at rest, scoped, permissioned)
- Risk disclosures, KYC/region notes — **compliance is on you; paper mode stays the default**

## Phase 6 — Monetization (optional)
- Free tier: paper account, public leaderboard
- Paid tier: more symbols, longer history, real-funds integration, priority cycles

---

### Current API surface (`/api/v1`)
| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/auth/register` | POST | no | create user + paper account |
| `/auth/login` | POST | no | get bearer token |
| `/me` | GET | yes | user + account info |
| `/me/portfolio` | GET | yes | equity, cash, PnL, positions |
| `/me/trades` | GET | yes | trade history |
| `/me/decisions` | GET | yes | every AI decision |
| `/me/cycle` | POST | yes | trigger one live cycle now |
| `/leaderboard` | GET | no | public top accounts |
| `/health` | GET | no | status |