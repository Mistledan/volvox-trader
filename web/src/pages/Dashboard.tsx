import { useCallback, useEffect, useState } from "react";
import { api, fmtUsd } from "../api";

interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  value_usd: number;
  unrealized_pnl_usd: number;
}
interface Portfolio {
  equity_usd: number;
  cash_usd: number;
  initial_balance_usd: number;
  pnl_usd: number;
  pnl_pct: number;
  realized_today_usd: number;
  positions: Position[];
  updated_at: string;
}
interface Decision {
  action: string;
  symbol: string;
  confidence: number;
  size: number;
  reasoning: string;
  status: string;
  timestamp: number;
}
interface TradeRec {
  time: number;
  side: string;
  symbol: string;
  quantity: number;
  price: number;
  value_usd: number;
  pnl_usd: number;
  reasoning: string;
}
interface LeaderRow {
  username: string;
  equity_usd: number;
  pnl_pct: number;
}

function pill(action: string): string {
  const a = action.toLowerCase();
  return a === "buy" ? "p-buy" : a === "sell" ? "p-sell" : "p-hold";
}
function fmtTs(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}
const cls = (n: number) => (n > 0 ? "pos" : n < 0 ? "neg" : "");

export default function Dashboard() {
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [trades, setTrades] = useState<TradeRec[]>([]);
  const [board, setBoard] = useState<LeaderRow[]>([]);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<string>("");
  const [err, setErr] = useState("");

  const load = useCallback(async (refresh = false) => {
    setErr("");
    try {
      const [p, d, t, lb] = (await Promise.all([
        api<Portfolio>("/api/v1/me/portfolio", refresh ? { cache: "no-store" } : undefined),
        api<{ decisions: Decision[] }>("/api/v1/me/decisions", refresh ? { cache: "no-store" } : undefined),
        api<{ trades: TradeRec[] }>("/api/v1/me/trades", refresh ? { cache: "no-store" } : undefined),
        api<{ users: LeaderRow[] }>("/api/v1/leaderboard"),
      ])) as [Portfolio, { decisions: Decision[] }, { trades: TradeRec[] }, { users: LeaderRow[] }];
      setPf(p);
      setDecisions(d.decisions);
      setTrades(t.trades);
      setBoard(lb.users);
    } catch (ex) {
      setErr(String((ex as Error).message));
    }
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
      const r = await api<{ decision: Decision; status: string; risk_ok: boolean }>(
        "/api/v1/me/cycle",
        { method: "POST" }
      );
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
    <div className="wrap">
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>Your portfolio</h1>
      <p className="muted" style={{ marginBottom: 16 }}>
        {pf ? `updated ${pf.updated_at}` : "loading…"}
      </p>

      {err && <div className="err" style={{ marginBottom: 12 }}>{err}</div>}

      <div className="cards">
        <div className="card">
          <div className="label">Equity</div>
          <div className="value">{pf ? fmtUsd(pf.equity_usd) : "…"}</div>
        </div>
        <div className="card">
          <div className="label">Cash</div>
          <div className="value">{pf ? fmtUsd(pf.cash_usd) : "…"}</div>
        </div>
        <div className="card">
          <div className="label">Total PnL</div>
          {pf && (
            <div className={`value ${cls(pf.pnl_usd)}`}>
              {pf.pnl_usd >= 0 ? "+" : ""}
              {fmtUsd(pf.pnl_usd)}
              <span className="muted" style={{ fontSize: 13 }}>
                {" "}
                ({pf.pnl_pct >= 0 ? "+" : ""}
                {pf.pnl_pct.toFixed(2)}%)
              </span>
            </div>
          )}
        </div>
        <div className="card">
          <div className="label">Realized today</div>
          {pf && (
            <div className={`value ${cls(pf.realized_today_usd)}`}>
              {pf.realized_today_usd >= 0 ? "+" : ""}
              {fmtUsd(pf.realized_today_usd)}
            </div>
          )}
        </div>
      </div>

      <div className="actions">
        <button className="btn primary" onClick={runCycle} disabled={running}>
          {running ? "AI is thinking…" : "Run an AI cycle now"}
        </button>
        {lastRun && <span className="muted" style={{ fontSize: 13 }}>last: {lastRun}</span>}
      </div>

      <div className="grid">
        <div className="panel">
          <h2>Positions</h2>
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
                    <td>{p.quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })}</td>
                    <td>{fmtUsd(p.avg_price)}</td>
                    <td>{fmtUsd(p.value_usd)}</td>
                    <td className={cls(p.unrealized_pnl_usd)}>{fmtUsd(p.unrealized_pnl_usd)}</td>
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
                    <td>{Math.round(d.confidence * 100)}%</td>
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
                    <td>{t.quantity.toLocaleString(undefined, { maximumFractionDigits: 6 })}</td>
                    <td>{fmtUsd(t.price)}</td>
                    <td className={cls(t.pnl_usd)}>{t.pnl_usd ? fmtUsd(t.pnl_usd) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel">
          <h2>Leaderboard</h2>
          {board.length === 0 ? (
            <p className="muted">No accounts yet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>User</th>
                  <th>Equity</th>
                  <th>PnL %</th>
                </tr>
              </thead>
              <tbody>
                {board.map((u, i) => (
                  <tr key={`${u.username}-${i}`}>
                    <td>{i + 1}</td>
                    <td>{u.username}</td>
                    <td>{fmtUsd(u.equity_usd)}</td>
                    <td className={cls(u.pnl_pct)}>
                      {u.pnl_pct >= 0 ? "+" : ""}
                      {u.pnl_pct.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <p className="muted" style={{ marginTop: 14 }}>
        Paper trading only — this is a simulation with virtual funds.
      </p>
    </div>
  );
}