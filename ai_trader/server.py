"""Volvox Trader SaaS backend: auth + multi-user paper trading API.

This is the API the future web app and mobile app will consume.
Run:  ai-trader-server   (or: python -m ai_trader.server)
Docs: http://127.0.0.1:8099/api/v1/docs  (OpenAPI)
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .api.autopilot import (
    equity_series,
    halted,
    record_equity_snapshot,
    run_autopilot_round,
    start_autopilot_worker,
)
from .api.ratelimit import GlobalRateLimitMiddleware, require_auth_rate_limit
from .auth import hash_password, new_token, token_expiry, token_hash, verify_password
from .config import PROJECT_ROOT, load_config
from .data.market_data import MarketData, MarketDataError
from .db import Account, ApiToken, DecisionRecord, User, init_db, session_scope
from .llm.client import LLMClient

cfg = load_config()
init_db()

_market: MarketData | None = None
_market_attempt = {"at": 0.0}
_market_cooldown_s = 30.0
_price_cache: dict[str, Any] = {"at": 0.0, "prices": {}}

WEB_DIST = PROJECT_ROOT / "web" / "dist"


class FakeLLM:
    """Deterministic stand-in when AI_TRADER_FAKE_LLM=1 (tests / demo)."""

    def complete_json(self, system: str, user: str, **kwargs) -> dict[str, Any]:
        return {"action": "hold", "symbol": "none", "confidence": 0.5, "order_size_usd": 0.0, "reasoning": "fake llm"}


def make_llm() -> LLMClient | FakeLLM:
    if os.getenv("AI_TRADER_FAKE_LLM") == "1":
        return FakeLLM()
    return LLMClient(cfg.llm)


def get_market() -> MarketData:
    global _market
    if _market is None:
        # Cooldown starts when a probe begins so concurrent/shortly-after
        # requests bail out instantly instead of each re-attempting the chain.
        if time.time() - _market_attempt["at"] < _market_cooldown_s:
            raise MarketDataError("market feed cooling down")
        _market_attempt["at"] = time.time()
        try:
            m = MarketData(cfg.exchanges)
            m.load_markets(cfg.symbols)
        except Exception:
            raise
        _market = m
    return _market


def current_prices(max_age_s: float = 15.0, budget_s: float = 6.0) -> dict[str, float]:
    global _price_cache
    now = time.time()
    if now - _price_cache["at"] < max_age_s:
        return _price_cache["prices"]
    prices: dict[str, float] = {}
    try:
        market = get_market()
        deadline = time.time() + budget_s
        for sym in cfg.symbols:
            if time.time() > deadline:
                break
            try:
                prices[sym] = market.fetch_ticker(sym)["last"]
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001 - no live marking without a feed
        pass
    _price_cache = {"at": now, "prices": prices}
    return prices


def _auth_user(authorization: str | None) -> tuple[User, Account]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="empty bearer token")
    with session_scope() as s:
        row = s.scalar(select(ApiToken).where(ApiToken.token_hash == token_hash(token)))
        if row is None:
            raise HTTPException(status_code=401, detail="invalid token")
        if row.expires_at is not None and row.expires_at < time.time():
            raise HTTPException(status_code=401, detail="token expired")
        row.last_used_at = time.time()
        user = s.get(User, row.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="user not found")
        account = s.scalar(select(Account).where(Account.user_id == user.id))
        if account is None:
            raise HTTPException(status_code=500, detail="account missing")
        return user, account


def _require_auth(authorization: str | None = Header(default=None, alias="Authorization")) -> tuple[User, Account]:
    return _auth_user(authorization)


app = FastAPI(title="Volvox Trader API", version="0.3.0", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GlobalRateLimitMiddleware)


class Credentials(BaseModel):
    username: str
    password: str


class AutopilotBody(BaseModel):
    enabled: bool


class CopyBody(BaseModel):
    leader_username: str | None = None


@contextmanager
def _store_for(account: Account) -> Iterator[Any]:
    from .api.dbstore import DbPortfolioStore

    yield DbPortfolioStore(account)


# ---- auth -----------------------------------------------------------
@app.post("/api/v1/auth/register", status_code=201)
def register(body: Credentials) -> dict[str, Any]:
    username = body.username.strip().lower()
    if not (3 <= len(username) <= 32) or not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="username must be 3-32 alphanumeric chars (_, - ok)")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")
    with session_scope() as s:
        if s.scalar(select(User).where(User.username == username)):
            raise HTTPException(status_code=409, detail="username already taken")
        user = User(username=username, password_hash=hash_password(body.password))
        s.add(user)
        s.flush()
        s.add(Account(user_id=user.id, name="paper", initial_balance=cfg.paper.initial_balance_usd,
                      cash_usd=cfg.paper.initial_balance_usd))
        token = new_token()
        s.add(ApiToken(user_id=user.id, token_hash=token_hash(token), expires_at=token_expiry()))
    return {"token": token, "token_type": "bearer", "username": username}


@app.post("/api/v1/auth/login")
def login(body: Credentials) -> dict[str, Any]:
    username = body.username.strip().lower()
    with session_scope() as s:
        user = s.scalar(select(User).where(User.username == username))
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid username or password")
        token = new_token()
        s.add(ApiToken(user_id=user.id, token_hash=token_hash(token), expires_at=token_expiry()))
    return {"token": token, "token_type": "bearer", "username": username}


@app.post("/api/v1/auth/refresh", dependencies=[Depends(require_auth_rate_limit)])
def refresh(auth: tuple[User, Account] = Depends(_require_auth)) -> dict[str, Any]:
    user, _ = auth
    with session_scope() as s:
        token = new_token()
        s.add(ApiToken(user_id=user.id, token_hash=token_hash(token), expires_at=token_expiry()))
    return {"token": token, "token_type": "bearer", "username": user.username}


def _account_state(s: Session, account: Account) -> dict[str, Any]:
    leader_username = None
    if account.leader_account_id:
        lacc = s.get(Account, account.leader_account_id)
        luser = s.get(User, lacc.user_id) if lacc else None
        leader_username = luser.username if luser else None
    return {
        "autopilot": bool(account.autopilot),
        "leader_username": leader_username,
        "last_cycle_at": account.last_cycle_at,
    }


# ---- account --------------------------------------------------------
@app.get("/api/v1/me")
def me(auth: tuple[User, Account] = Depends(_require_auth)) -> dict[str, Any]:
    user, account = auth
    with session_scope() as s:
        acc = s.get(Account, account.id)
        state = _account_state(s, acc if acc else account)
    return {
        "id": user.id,
        "username": user.username,
        "created_at": user.created_at,
        "account_id": account.id,
        "initial_balance_usd": account.initial_balance,
        **state,
    }


@app.post("/api/v1/me/autopilot")
def set_autopilot(
    body: AutopilotBody,
    auth: tuple[User, Account] = Depends(_require_auth),
) -> dict[str, Any]:
    _, account = auth
    with session_scope() as s:
        acc = s.get(Account, account.id)
        acc.autopilot = 1 if body.enabled else 0
        return _account_state(s, acc)


@app.post("/api/v1/me/copy")
def set_copy(
    body: CopyBody,
    auth: tuple[User, Account] = Depends(_require_auth),
) -> dict[str, Any]:
    user, account = auth
    leader_id = None
    if body.leader_username:
        name = body.leader_username.strip().lower()
        with session_scope() as s:
            luser = s.scalar(select(User).where(User.username == name))
            if luser is None:
                raise HTTPException(status_code=404, detail="leader not found")
            if luser.id == user.id:
                raise HTTPException(status_code=400, detail="cannot copy yourself")
            lacc = s.scalar(select(Account).where(Account.user_id == luser.id))
            if lacc is None:
                raise HTTPException(status_code=404, detail="leader has no account")
            leader_id = lacc.id
    with session_scope() as s:
        acc = s.get(Account, account.id)
        acc.leader_account_id = leader_id
        return _account_state(s, acc)


@app.get("/api/v1/me/portfolio")
def portfolio(auth: tuple[User, Account] = Depends(_require_auth)) -> dict[str, Any]:
    user, account = auth
    with _store_for(account) as store:
        prices = current_prices()
        store.update_prices(prices)
        equity = store.equity(prices)
        init = store.initial_balance
        record_equity_snapshot(account.id, equity)
        positions = [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_price": p.avg_price,
                "value_usd": round(p.quantity * prices.get(p.symbol, p.avg_price), 2),
                "unrealized_pnl_usd": round(p.quantity * (prices.get(p.symbol, p.avg_price) - p.avg_price), 2),
            }
            for p in store.positions.values()
        ]
        return {
            "username": user.username,
            "equity_usd": round(equity, 2),
            "cash_usd": store.cash,
            "initial_balance_usd": init,
            "pnl_usd": round(equity - init, 2),
            "pnl_pct": round((equity - init) / init * 100.0, 3) if init else 0.0,
            "realized_today_usd": round(store.realized_today(), 2),
            "daily_loss_halted": halted(cfg, store, prices) is not None,
            "positions": positions,
            "prices": prices,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }


@app.get("/api/v1/me/equity")
def equity_history(auth: tuple[User, Account] = Depends(_require_auth)) -> dict[str, Any]:
    _, account = auth
    return {"points": equity_series(account.id, limit=200)}


@app.get("/api/v1/me/trades")
def trades(auth: tuple[User, Account] = Depends(_require_auth)) -> dict[str, list[dict[str, Any]]]:
    _, account = auth
    with _store_for(account) as store:
        return {
            "trades": [
                {
                    "time": t.timestamp,
                    "side": t.side,
                    "symbol": t.symbol,
                    "quantity": t.quantity,
                    "price": t.price,
                    "value_usd": t.value_usd,
                    "pnl_usd": t.pnl_usd,
                    "confidence": t.confidence,
                    "reasoning": t.reasoning,
                }
                for t in store.trades[:50]
            ]
        }


@app.get("/api/v1/me/decisions")
def decisions(auth: tuple[User, Account] = Depends(_require_auth)) -> dict[str, list[dict[str, Any]]]:
    _, account = auth
    with _store_for(account) as store:
        return {"decisions": store.decisions(limit=50)}


@app.post("/api/v1/me/cycle")
def run_cycle_now(auth: tuple[User, Account] = Depends(_require_auth)) -> dict[str, Any]:
    from .api.dbstore import DbPortfolioStore
    from .api.engine import portfolio_summary, run_cycle

    _, account = auth
    llm = make_llm()
    with _store_for(account) as store:
        prices = current_prices()
        store.update_prices(prices)
        reason = halted(cfg, store, prices)
        if reason:
            decision = {"action": "hold", "symbol": "none", "confidence": 0.0, "order_size_usd": 0.0, "reasoning": reason}
            store.record_decision(decision, "halted")
            record_equity_snapshot(account.id, store.equity(prices))
            return {
                "decision": decision,
                "risk_ok": False,
                "risk_checks": [reason],
                "status": "halted",
                "trade": None,
                "portfolio": portfolio_summary(store, prices),
            }
        try:
            market = get_market()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=503, detail=f"no reachable market feed: {exc}")
        result = run_cycle(store, market, llm, cfg)
        decision = result.get("decision", {})
        record_equity_snapshot(account.id, result.get("portfolio", {}).get("equity_usd", store.equity(result.get("prices", {}))))
        return {
            "decision": decision,
            "risk_ok": result.get("risk_ok"),
            "risk_checks": result.get("risk_checks", []),
            "status": result.get("status", "noop"),
            "trade": {
                "side": result["trade"].side,
                "symbol": result["trade"].symbol,
                "quantity": result["trade"].quantity,
                "price": result["trade"].price,
            }
            if result.get("trade")
            else None,
            "portfolio": portfolio_summary(store, result.get("prices", {})),
        }


# ---- public ---------------------------------------------------------
@app.get("/api/v1/leaderboard")
def leaderboard() -> dict[str, list[dict[str, Any]]]:
    prices = current_prices()
    from .api.dbstore import DbPortfolioStore

    with session_scope() as s:
        accounts = s.scalars(select(Account).order_by(Account.created_at)).all()
        rows = []
        for acc in accounts:
            user = s.get(User, acc.user_id)
            store = DbPortfolioStore(acc)
            store.update_prices(prices)
            equity = store.equity(prices)
            init = acc.initial_balance or 1.0
            rows.append({
                "username": user.username if user else "?",
                "autopilot": bool(acc.autopilot),
                "equity_usd": round(equity, 2),
                "pnl_pct": round((equity - init) / init * 100.0, 3),
                "updated_at": acc.created_at,
            })
        rows.sort(key=lambda r: r["equity_usd"], reverse=True)
        return {"users": rows[:20]}


@app.get("/api/v1/markets")
def markets() -> dict[str, Any]:
    prices = current_prices()
    return {
        "markets": [{"symbol": sym, "last": float(px)} for sym, px in prices.items()],
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/api/v1/signals")
def signals() -> dict[str, list[dict[str, Any]]]:
    """Latest AI decisions across all accounts (public signals feed)."""
    with session_scope() as s:
        rows = (
            s.execute(
                select(DecisionRecord, User, Account)
                .join(Account, Account.id == DecisionRecord.account_id)
                .join(User, User.id == Account.user_id)
                .order_by(DecisionRecord.timestamp.desc())
                .limit(30)
            )
            .all()
        )
        out = []
        for rec, user, _acc in rows:
            if rec.action == "hold" and rec.status == "noop":
                continue
            out.append({
                "username": user.username,
                "action": rec.action,
                "symbol": rec.symbol,
                "confidence": rec.confidence,
                "size": rec.size,
                "reasoning": rec.reasoning,
                "status": rec.status,
                "time": rec.timestamp,
            })
        return {"signals": out}


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "mode": cfg.mode, "llm": cfg.llm.provider, "model": cfg.llm.model}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    web_index = WEB_DIST / "index.html"
    if web_index.is_file():
        return FileResponse(web_index)
    return (
        "<html><body style='font-family:system-ui;background:#0b1020;color:#e6edf7;padding:32px'><h1>Volvox Trader API</h1>"
        "<p>Multi-user paper-trading backend.</p>"
        "<ul>"
        "<li>OpenAPI docs: <a href='/api/v1/docs'>/api/v1/docs</a></li>"
        "<li>Health: <a href='/api/v1/health'>/api/v1/health</a></li>"
        "<li>Leaderboard: <a href='/api/v1/leaderboard'>/api/v1/leaderboard</a></li>"
        "</ul></body></html>"
    )


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> Any:
    """Serve the built SPA (web/dist) with fallback to index.html for client routes."""
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="unknown API endpoint")
    if WEB_DIST.is_dir():
        candidate = (WEB_DIST / path).resolve()
        try:
            candidate.relative_to(WEB_DIST.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="bad path") from exc
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
    raise HTTPException(status_code=404, detail="web application not built")


def main() -> None:
    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", "8099"))
    start_autopilot_worker(cfg, get_market, make_llm)
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()