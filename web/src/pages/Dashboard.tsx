import { useCallback, useEffect, useState } from "react";
import { api, fmtPct, fmtQty, fmtTs, fmtUsd } from "../api";
import EquityChart, { type EquityPoint } from "../components/EquityChart";
import type { Decision, Me, Portfolio, TradeRec } from "../types";

function pill(action: string): string {
  const a = action.toLowerCase();
  return a === "buy" ? "p-buy" : a === "sell" ? "p-sell" : "p-hold";
}
const cls = (n: number) => (n > 0 ? "pos" : n < 0 ? "neg" : "");

export default function Dashboard() {
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [equity, setEquity] = useState<EquityPoint[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [trades, setTrades] = useState<TradeRec[]>([]);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async (refresh = false) => {
    setErr("");
    const opts: RequestInit = refresh ? { cache: "no-store" } : {};
    const rec = <T,>(p: string, set: (v: T) => void) => {
      const c = new AbortController();
      const to = setTimeout(() => c.abort(), 20000);
      return api<T>(p, { ...opts, signal: c.signal })
        .then(set)
        .catch((ex: unknown) => {
          if ((ex as Error).name === "AbortError") return;
          setErr(`${p.split("/").pop()}: ${(ex as Error).message}`);
        })
        .finally(() => clearTimeout(to));
    };
    await Promise.allSettled([
      rec<Portfolio>("/api/v1/me/portfolio", setPf),
      rec<{ decisions: Decision[] }>("/api/v1/me/decisions", (j) => setDecisions(j.decisions)),
      rec<{ trades: TradeRec[] }>("/api/v1/me/trades", (j) => setTrades(j.trades)),
      rec<{ points: EquityPoint[] }>("/api/v1/me/equity", (j) => setEquity(j.points)),
      rec<Me>("/api/v1/me", setMe),
    ]);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => load(true), 15000);
    return () => clearInterval(t);
  }, [load]);

  async function runCycle() {
    if (running) return;
    setRunning(true);
    setErr("");
    setLastRun("…thinking");
    try {
      const r = await api<{ decision: Decision; status: string }>("/api/v1/me/cycle", {
        method: "POST",
      });
      setLastRun(
        `${r.decision.action.toUpperCase()} · ${r.decision.symbol} · conf ${Math.round(
          r.decision.confidence * 100
        )}% · ${r.status}`
      );
      await load(true);
    } catch (ex) {
      setErr(String((ex as Error).message));
      setLastRun("");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <h1 style={{ fontSize: 20 }}>Overview</h1>
      <p className="muted" style={{ marginTop: 2, marginBottom: 14 }}>
        {pf ? `updated ${pf.updated_at}` : "loading…"} ·{" "}
        {me?.autopilot ? (
          <span className="pos">autopilot ON</span>
        ) : (
          <span className="muted">autopilot off</span>
        )}
        {me?.leader_username ? <> · following {me.leader_username}</> : null}
      </p>

      {err && <div className="err" style={{ marginBottom: 12 }}>{err}</div>}

      {pf?.daily_loss_halted && (
        <div className="halted-banner">
          Daily loss limit reached — the risk circuit breaker has paused new positions for today.
        </div>
      )}

      <div className="cards">
        <div className="card">
          <div className="label">Equity</div>
          <div className={`value mono ${pf ? cls(pf.pnl_usd) : ""}`}>{pf ? fmtUsd(pf.equity_usd) : "…"}</div>
        </div>
        <div className="card">
          <div className="label">Cash</div>
          <div className="value mono">{pf ? fmtUsd(pf.cash_usd) : "…"}</div>
        </div>
        <div className="card">
          <div className="label">Total PnL</div>
          {pf && (
            <div className={`value mono ${cls(pf.pnl_usd)}`}>
              {pf.pnl_usd >= 0 ? "+" : ""}
              {fmtUsd(pf.pnl_usd)}
              <span className="muted" style={{ fontSize: 13 }}>
                {" "}
                ({fmtPct(pf.pnl_pct)})
              </span>
            </div>
          )}
        </div>
        <div className="card">
          <div className="label">Realized today</div>
          {pf && (
            <div className={`value mono ${cls(pf.realized_today_usd)}`}>
              {pf.realized_today_usd >= 0 ? "+" : ""}
              {fmtUsd(pf.realized_today_usd)}
            </div>
          )}
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 12 }}>
        <h2>
          Equity history
          <span className="right muted">
            {equity.length ? `${equity.length} point(s)` : "no data yet"}
          </span>
        </h2>
        <EquityChart points={equity} baseline={pf?.initial_balance_usd} />
      </div>

      <div className="actions">
        <button className="btn primary" onClick={runCycle} disabled={running}>
          {running ? "AI is thinking…" : "Run an AI cycle now"}
        </button>
        <button className="btn" onClick={() => load(true)}>
          Refresh
        </button>
        {lastRun && (
          <span className="muted" style={{ fontSize: 13 }}>
            last: {lastRun}
          </span>
        )}
      </div>

      <div className="grid">
        <div className="panel">
          <h2>Open positions</h2>
          {!pf || pf.positions.length === 0 ? (
            <p className="muted">No open positions.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Qty</th>
                  <th>Avg</th>
                  <th>Value</th>
                  <th>uPnL</th>
                </tr>
              </thead>
              <tbody>
                {pf.positions.map((p) => (
                  <tr key={p.symbol}>
                    <td>{p.symbol}</td>
                    <td className="mono">{fmtQty(p.quantity)}</td>
                    <td className="mono">{fmtUsd(p.avg_price)}</td>
                    <td className="mono">{fmtUsd(p.value_usd)}</td>
                    <td className={`mono ${cls(p.unrealized_pnl_usd)}`}>{fmtUsd(p.unrealized_pnl_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel">
          <h2>AI decisions</h2>
          {decisions.length === 0 ? (
            <p className="muted">No decisions yet — run a cycle.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Action</th>
                  <th>Conf</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {decisions.slice(0, 15).map((d, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtTs(d.timestamp)}</td>
                    <td>
                      <span className={`pill ${pill(d.action)}`}>{d.action.toUpperCase()}</span>
                    </td>
                    <td className="mono">{Math.round(d.confidence * 100)}%</td>
                    <td className="muted">{d.reasoning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="grid">
        <div className="panel">
          <h2>Trade history</h2>
          {trades.length === 0 ? (
            <p className="muted">No trades yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Side</th>
                  <th>Symbol</th>
                  <th>Qty</th>
                  <th>Price</th>
                  <th>PnL</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtTs(t.time)}</td>
                    <td>
                      <span className={`pill ${pill(t.side)}`}>{t.side.toUpperCase()}</span>
                    </td>
                    <td>{t.symbol}</td>
                    <td className="mono">{fmtQty(t.quantity)}</td>
                    <td className="mono">{fmtUsd(t.price)}</td>
                    <td className={`mono ${cls(t.pnl_usd)}`}>{t.pnl_usd ? fmtUsd(t.pnl_usd) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel">
          <h2>Quick status</h2>
          <ul className="list" style={{ marginLeft: 0, listStyle: "none" }}>
            <li>
              <b>Autopilot</b> —{" "}
              {me?.autopilot ? <span className="pos">running</span> : <span className="muted">off</span>}{" "}
              {me?.last_cycle_at ? (
                <span className="muted">(last cycle {fmtTs(me.last_cycle_at)})</span>
              ) : null}
            </li>
            <li>
              <b>Copy</b> —{" "}
              {me?.leader_username ? (
                <span>
                  following <b>{me.leader_username}</b>
                </span>
              ) : (
                <span className="muted">none</span>
              )}
            </li>
            <li>
              <b>Mode</b> — <span className="muted">100% paper (simulated funds)</span>
            </li>
            <li>
              <b>Risk</b> — daily-loss halt, position caps, confidence floor active.
            </li>
          </ul>
          <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            Tune autopilot and copy trading from <a href="/settings">Bot settings</a>.
          </p>
        </div>
      </div>
    </>
  );
}