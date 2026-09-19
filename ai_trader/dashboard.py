"""Local live dashboard for AI-Trader.

Run with:  python -m ai_trader.dashboard   (or: ai-trader-dashboard)
Opens at http://127.0.0.1:8079

Reads the paper state file + log file written by the running bot, so it can be
started/stopped independently without touching the trading loop.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

from .config import PROJECT_ROOT, load_config
from .data.market_data import MarketData
from .utils.logging import get_logger

load_dotenv(PROJECT_ROOT / ".env")
log = get_logger("ai_trader.dashboard")

cfg = load_config()
DATA_FILE = cfg.data_file_path
LOG_FILE = cfg.log_file_path

_prices_cache: dict[str, Any] = {"at": 0.0, "prices": {}}
_market: MarketData | None = None

DECISION_RE = re.compile(r"decision action=(\w+) symbol=([\w/-]+) confidence=([\d.]+) size=([\d.eE+-]+)")
CYCLE_RE = re.compile(r"--- CYCLE RESULT: (\w+) \| status=(\w+)")

app = FastAPI(title="AI-Trader Dashboard")


def _ensure_market() -> MarketData | None:
    global _market
    if _market is None:
        try:
            m = MarketData(cfg.exchanges)
            m.load_markets(cfg.symbols)
            _market = m
        except Exception as exc:  # noqa: BLE001 - dashboard must not crash
            log.warning("Dashboard market feed unavailable: %s", exc)
            _market = None
    return _market


def _current_prices(max_age_s: float = 30.0) -> dict[str, float]:
    global _prices_cache
    now = time.time()
    if now - _prices_cache["at"] < max_age_s:
        return _prices_cache["prices"]
    prices: dict[str, float] = {}
    m = _ensure_market()
    if m is not None:
        for sym in cfg.symbols:
            try:
                prices[sym] = m.fetch_ticker(sym)["last"]
            except Exception:  # noqa: BLE001
                pass
    _prices_cache = {"at": now, "prices": prices}
    return prices


def _read_state() -> dict[str, Any]:
    default = {
        "initial_balance": cfg.paper.initial_balance_usd,
        "cash_usd": cfg.paper.initial_balance_usd,
        "positions": {},
        "trades": [],
        "last_pnl_per_day": {},
    }
    if not DATA_FILE.exists():
        return default
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _parse_events(limit: int = 60) -> list[dict[str, Any]]:
    if not LOG_FILE.exists():
        return []
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines:
        ts = line[:19]
        dm = DECISION_RE.search(line)
        if dm:
            events.append({
                "event": "decision",
                "time": ts,
                "action": dm.group(1),
                "symbol": dm.group(2),
                "confidence": float(dm.group(3)),
                "size": float(dm.group(4)),
            })
            continue
        cm = CYCLE_RE.search(line)
        if cm:
            events.append({
                "event": "cycle",
                "time": ts,
                "action": cm.group(1),
                "status": cm.group(2),
            })
    return events[-limit:]


def _fmt_ts(ts: float) -> str:
    try:
        return time.strftime("%m-%d %H:%M:%S", time.localtime(ts))
    except (OSError, ValueError):
        return "?"


def _compute(state: dict[str, Any], prices: dict[str, float]) -> dict[str, Any]:
    init = float(state.get("initial_balance", cfg.paper.initial_balance_usd))
    cash = float(state.get("cash_usd", init))
    positions = state.get("positions", {})
    equity = cash
    pos_rows = []
    for sym, pos in positions.items():
        qty = float(pos.get("quantity", 0.0))
        avg = float(pos.get("avg_price", 0.0))
        px = prices.get(sym, avg)
        equity += qty * px
        pos_rows.append({
            "symbol": sym,
            "quantity": qty,
            "avg_price": avg,
            "last_price": px,
            "value_usd": qty * px,
        })
    today = time.strftime("%Y-%m-%d", time.gmtime())
    realized_today = float(state.get("last_pnl_per_day", {}).get(today, 0.0))
    trades = []
    for t in reversed(state.get("trades", [])[-30:]):
        trades.append({
            "time": _fmt_ts(float(t.get("timestamp", 0.0))),
            "side": t.get("side", "?"),
            "symbol": t.get("symbol", "?"),
            "quantity": float(t.get("quantity", 0.0)),
            "price": float(t.get("price", 0.0)),
            "value_usd": float(t.get("value_usd", 0.0)),
            "pnl_usd": float(t.get("pnl_usd", 0.0)),
            "confidence": float(t.get("confidence", 0.0)),
        })
    pnl = equity - init
    return {
        "equity_usd": equity,
        "cash_usd": cash,
        "initial_balance_usd": init,
        "pnl_usd": pnl,
        "pnl_pct": (pnl / init * 100.0) if init else 0.0,
        "realized_today_usd": realized_today,
        "prices": {s: {"last": px} for s, px in prices.items()},
        "positions": pos_rows,
        "trades": trades,
        "events": list(reversed(_parse_events(40))),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


@app.get("/api/state")
def api_state() -> dict[str, Any]:
    state = _read_state()
    prices = _current_prices()
    return _compute(state, prices)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AI-Trader Dashboard</title>
<style>
  :root { --bg:#0b1020; --card:#121a2e; --line:#1f2a44; --txt:#dbe4f5; --dim:#7d8db0;
          --green:#2ecc71; --red:#e74c3c; --amber:#f1c40f; --blue:#4aa3ff; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--txt); font:14px/1.5 Segoe UI, system-ui, sans-serif;
         padding:20px; }
  h1 { font-size:20px; margin-bottom:4px; }
  .sub { color:var(--dim); margin-bottom:16px; font-size:12px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:16px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; }
  .card .label { color:var(--dim); font-size:11px; text-transform:uppercase; letter-spacing:.5px; }
  .card .value { font-size:24px; font-weight:600; margin-top:4px; }
  .pos { color:var(--green); } .neg { color:var(--red); }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:12px; margin-bottom:12px; }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; overflow:hidden; }
  .panel h2 { font-size:13px; text-transform:uppercase; letter-spacing:.5px; color:var(--dim); margin-bottom:10px; }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th { color:var(--dim); text-align:left; font-weight:500; padding:6px 8px; border-bottom:1px solid var(--line); }
  td { padding:6px 8px; border-bottom:1px solid #161f36; }
  tr:last-child td { border-bottom:none; }
  .badge { display:inline-block; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; }
  .b-buy { background:rgba(46,204,113,.15); color:var(--green); }
  .b-sell { background:rgba(231,76,60,.15); color:var(--red); }
  .b-hold { background:rgba(241,196,15,.15); color:var(--amber); }
  .ready { color:var(--green); } .stale { color:var(--red); }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
</style>
</head>
<body>
  <h1>AI-Trader <span style="color:var(--blue)">Live Dashboard</span></h1>
  <div class="sub" id="status">Connecting...</div>
  <div class="cards" id="cards"></div>
  <div class="grid">
    <div class="panel"><h2>Positions</h2><table id="pos"></table></div>
    <div class="panel"><h2>Prices</h2><table id="prices"></table></div>
    <div class="panel"><h2>Agent Decisions</h2><table id="decisions"></table></div>
    <div class="panel"><h2>Recent Trades</h2><table id="trades"></table></div>
  </div>
<script>
const $ = (id) => document.getElementById(id);
function fmt(n, d) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return n.toLocaleString(undefined, { minimumFractionDigits: d || 2, maximumFractionDigits: d || 2 });
}
function cls(n) { return n > 0 ? "pos" : n < 0 ? "neg" : ""; }
function badge(a) {
  const c = a.toLowerCase();
  const k = c === "buy" ? "b-buy" : c === "sell" ? "b-sell" : "b-hold";
  return `<span class="badge ${k}">${a.toUpperCase()}</span>`;
}
function render(s) {
  $("status").innerHTML =
    `<span class="dot ${false ? "stale" : "ready"}"></span>Paper mode &middot; updated ${s.updated_at} &middot; ` +
    `${Object.keys(s.prices).length} symbol(s)`;
  $("cards").innerHTML = `
    <div class="card"><div class="label">Equity</div><div class="value">$${fmt(s.equity_usd)}</div></div>
    <div class="card"><div class="label">Cash</div><div class="value">$${fmt(s.cash_usd)}</div></div>
    <div class="card"><div class="label">Total PnL</div><div class="value ${cls(s.pnl_usd)}">${s.pnl_usd >= 0 ? "+" : ""}$${fmt(s.pnl_usd)} <span style="font-size:13px;color:var(--dim)">(${s.pnl_pct >= 0 ? "+" : ""}${fmt(s.pnl_pct, 2)}%)</span></div></div>
    <div class="card"><div class="label">Realized Today</div><div class="value ${cls(s.realized_today_usd)}">${s.realized_today_usd >= 0 ? "+" : ""}$${fmt(s.realized_today_usd)}</div></div>`;
  $("pos").innerHTML = s.positions.length
    ? "<tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Last</th><th>Value</th></tr>" +
      s.positions.map(p => `<tr><td>${p.symbol}</td><td>${fmt(p.quantity, 6)}</td><td>$${fmt(p.avg_price)}</td><td>$${fmt(p.last_price)}</td><td>$${fmt(p.value_usd)}</td></tr>`).join("")
    : "<tr><td style='color:var(--dim)'>No open positions</td></tr>";
  $("prices").innerHTML = "<tr><th>Symbol</th><th>Last Price</th></tr>" +
    Object.entries(s.prices).map(([k, v]) => `<tr><td>${k}</td><td>$${fmt(v.last)}</td></tr>`).join("") +
    (Object.keys(s.prices).length ? "" : "<tr><td style='color:var(--dim)'>No live prices</td></tr>");
  $("decisions").innerHTML = s.events.length
    ? "<tr><th>Time</th><th>Action</th><th>Symbol</th><th>Conf</th></tr>" +
      s.events.filter(e => e.event === "decision").slice(0, 20).map(e =>
        `<tr><td>${e.time}</td><td>${badge(e.action)}</td><td>${e.symbol}</td><td>${fmt(e.confidence * 100, 0)}%</td></tr>`).join("")
    : "<tr><td style='color:var(--dim)'>No decisions yet</td></tr>";
  $("trades").innerHTML = s.trades.length
    ? "<tr><th>Time</th><th>Side</th><th>Symbol</th><th>Qty</th><th>Price</th><th>Value</th><th>PnL</th></tr>" +
      s.trades.map(t =>
        `<tr><td>${t.time}</td><td>${badge(t.side)}</td><td>${t.symbol}</td><td>${fmt(t.quantity, 6)}</td><td>$${fmt(t.price)}</td><td>$${fmt(t.value_usd)}</td><td style="color:${cls(t.pnl_usd)}">${t.pnl_usd !== 0 ? (t.pnl_usd > 0 ? "+" : "") + "$" + fmt(t.pnl_usd) : "-"}</td></tr>`).join("")
    : "<tr><td style='color:var(--dim)'>No trades yet</td></tr>";
}
async function tick() {
  try {
    const r = await fetch("/api/state");
    render(await r.json());
  } catch (e) {
    $("status").innerHTML = `<span class="dot stale"></span>Dashboard API unreachable (${e})`;
  }
}
tick();
setInterval(tick, 5000);
</script>
</body>
</html>
"""


def main() -> None:
    host, port = "127.0.0.1", 8079
    log.info("Dashboard: http://%s:%d  (reads %s)", host, port, DATA_FILE)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()