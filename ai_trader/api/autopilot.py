"""Autonomous per-account scheduling + copy-trading over the SaaS API.

The API server runs one daemon worker that, on every ``cycle_seconds``,
cycles through every account with autopilot enabled. Accounts that follow a
leader (``leader_account_id``) mirror the leader's positions instead of
running their own AI decision; everyone else runs the normal
strategy/risk/execution pipeline.

All market access goes through callables provided by the server module to
avoid a circular import.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

from sqlalchemy import select

from ..config import Config
from ..db import Account, EquitySnapshot, Holding, session_scope
from ..trading.store import PortfolioStore
from .dbstore import DbPortfolioStore
from .engine import run_cycle

log = logging.getLogger("ai_trader.autopilot")

MIN_NOTIONAL = 5.0

_worker: threading.Thread | None = None
_active: set[int] = set()
_active_lock = threading.Lock()


# ---- circuit breaker --------------------------------------------------
def halted(cfg: Config, store: PortfolioStore, prices: dict[str, float]) -> str | None:
    """Return a reason if the account is circuit-broken, else None."""
    equity = store.equity(prices)
    if store.realized_today() < -cfg.risk.max_daily_loss_pct * equity:
        return "daily loss limit reached"
    if equity <= 0:
        return "equity depleted"
    return None


# ---- equity history ---------------------------------------------------
def record_equity_snapshot(account_id: int, equity: float) -> None:
    try:
        with session_scope() as s:
            s.add(EquitySnapshot(account_id=account_id, equity=float(equity), timestamp=time.time()))
    except Exception as exc:  # noqa: BLE001 - never let history break a cycle
        log.warning("equity snapshot failed for account %s: %s", account_id, exc)


def equity_series(account_id: int, limit: int = 200) -> list[dict[str, float]]:
    with session_scope() as s:
        rows = (
            s.scalars(
                select(EquitySnapshot)
                .where(EquitySnapshot.account_id == account_id)
                .order_by(EquitySnapshot.timestamp.asc())
                .limit(limit)
            )
            .all()
        )
        return [{"ts": r.timestamp, "equity": r.equity} for r in rows]


# ---- copy trading -----------------------------------------------------
def copy_from_leader(
    store: PortfolioStore,
    leader_account_id: int,
    prices: dict[str, float],
    cfg: Config,
) -> None:
    """Rebalance ``store`` to mirror the leader's position weights."""
    with session_scope() as s:
        leader = s.get(Account, leader_account_id)
        if leader is None:
            raise ValueError("leader account gone")
        leader_holdings = {
            r.symbol: r.quantity
            for r in s.scalars(select(Holding).where(Holding.account_id == leader.id)).all()
            if r.quantity > 1e-12
        }

    leader_store = DbPortfolioStore(leader)
    leader_store.update_prices(prices)
    leader_equity = leader_store.equity(prices)
    if leader_equity <= 0:
        raise ValueError("leader equity non-positive")

    targets: dict[str, float] = {}
    for sym, qty in leader_holdings.items():
        px = prices.get(sym, 0.0)
        if px > 0:
            targets[sym] = qty * px / leader_equity

    fol_equity = store.equity(prices)
    if fol_equity <= 0:
        raise ValueError("follower equity non-positive")

    positions = store.positions
    for sym in set(targets) | set(positions):
        px = prices.get(sym, 0.0)
        if px <= 0:
            continue
        cur_val = positions[sym].quantity * px if sym in positions else 0.0
        target_val = targets.get(sym, 0.0) * fol_equity
        delta = target_val - cur_val
        if sym not in targets and cur_val <= MIN_NOTIONAL:
            continue
        try:
            if delta > MIN_NOTIONAL:
                store.market_buy(sym, delta, px, reason=f"copy leader #{leader_account_id}", confidence=1.0)
            elif delta < -MIN_NOTIONAL:
                qty = min(-delta / px, positions[sym].quantity if sym in positions else 0.0)
                if qty > 0:
                    store.market_sell(sym, qty, px, reason=f"copy leader #{leader_account_id}", confidence=1.0)
        except ValueError as exc:
            log.warning("copy order failed (%s): %s", sym, exc)

    store.record_decision(
        {
            "action": "copy",
            "symbol": "none",
            "confidence": 1.0,
            "order_size_usd": 0.0,
            "reasoning": f"mirrored leader account {leader_account_id}",
        },
        "copied",
    )


# ---- per-account cycle -------------------------------------------------
def run_account_cycle(account: Account, market, llm, cfg: Config) -> dict[str, Any]:
    store = DbPortfolioStore(account)
    prices: dict[str, float] = {}
    for symbol in cfg.symbols:
        try:
            prices[symbol] = market.fetch_ticker(symbol)["last"]
        except Exception:  # noqa: BLE001 - proceed with whatever we have
            pass
    store.update_prices(prices)

    result: dict[str, Any] = {}
    try:
        reason = halted(cfg, store, prices)
        if reason:
            store.record_decision(
                {"action": "hold", "symbol": "none", "confidence": 0.0, "order_size_usd": 0.0, "reasoning": reason},
                "halted",
            )
            result = {"status": "halted", "reason": reason}
        elif account.leader_account_id:
            copy_from_leader(store, account.leader_account_id, prices, cfg)
            result = {"status": "copied"}
        else:
            result = run_cycle(store, market, llm, cfg)
    finally:
        record_equity_snapshot(account.id, store.equity(prices))
        with session_scope() as s:
            acc = s.get(Account, account.id)
            if acc is not None:
                acc.last_cycle_at = time.time()
    return result


# ---- round + worker ---------------------------------------------------
def run_autopilot_round(
    cfg: Config,
    make_market: Callable[[], Any],
    make_llm: Callable[[], Any],
) -> dict[str, Any]:
    """One sweep over every autopilot-enabled account (serially)."""
    with session_scope() as s:
        accounts = s.scalars(select(Account).where(Account.autopilot == 1)).all()
        todo = [(a.id, a.leader_account_id) for a in accounts]
    if not todo:
        return {"accounts": [], "errors": {}}

    try:
        market = make_market()
    except Exception as exc:  # noqa: BLE001 - no feed, run nothing this round
        log.warning("autopilot round skipped (market unreachable): %s", exc)
        return {"accounts": [aid for aid, _ in todo], "errors": {"market": str(exc)}}
    llm = make_llm()

    errors: dict[int, str] = {}
    ran: list[int] = []
    for aid, leader_id in todo:
        with _active_lock:
            if aid in _active:
                continue
            _active.add(aid)
        try:
            run_account_cycle(Account(id=aid, initial_balance=0.0, autopilot=1, leader_account_id=leader_id), market, llm, cfg)
            ran.append(aid)
        except Exception as exc:  # noqa: BLE001 - isolated per account
            log.warning("autopilot account %s failed: %s", aid, exc)
            errors[aid] = str(exc)
        finally:
            with _active_lock:
                _active.discard(aid)
    return {"accounts": ran, "errors": errors}


def start_autopilot_worker(
    cfg: Config,
    make_market: Callable[[], Any],
    make_llm: Callable[[], Any],
    interval_s: int | None = None,
) -> threading.Thread:
    """Start (if not running) the background autopilot daemon."""
    global _worker
    if _worker is not None and _worker.is_alive():
        return _worker
    interval = interval_s or int(os.getenv("AUTOPILOT_SECONDS", str(cfg.cycle_seconds)))

    def loop() -> None:
        while True:
            try:
                run_autopilot_round(cfg, make_market, make_llm)
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                log.warning("autopilot round failed: %s", exc)
            time.sleep(max(5, interval))

    _worker = threading.Thread(target=loop, name="autopilot", daemon=True)
    _worker.start()
    log.info("autopilot worker started (interval=%ss)", interval)
    return _worker