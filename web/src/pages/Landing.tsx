import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API_URL } from "../api";

interface LeaderRow {
  username: string;
  equity_usd: number;
  pnl_pct: number;
}

export default function Landing() {
  const [board, setBoard] = useState<LeaderRow[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api<{ users: LeaderRow[] }>("/api/v1/leaderboard")
      .then((j) => {
        setBoard(j.users);
        setOnline(true);
      })
      .catch(() => setOnline(false));
    const t = setInterval(() => {
      api<{ users: LeaderRow[] }>("/api/v1/leaderboard")
        .then((j) => {
          setBoard(j.users);
          setOnline(true);
        })
        .catch(() => setOnline(false));
    }, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="wrap">
      <div className="hero">
        <h1>
          AI trading that never sleeps — <span style={{ color: "var(--blue)" }}>and never blinks</span>
        </h1>
        <p className="sub">
          Volvox Trader is a 100% fully-automated, agent-native trading bot. An AI
          reads the live market, reasons about it, and trades a paper account — with
          no human in the loop. Watch every decision, in real time.
        </p>
        <div className="badge-row">
          <span className={`btn ${online ? "primary" : ""}`} style={{ cursor: "default" }}>
            {online === null ? "…connecting" : online ? "● API online" : "○ API offline"}
          </span>
          <Link to="/register" className="btn primary">
            Try it — free paper account
          </Link>
          <Link to="/login" className="btn">
            Log in
          </Link>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 18 }}>
        <h2>How the agent thinks <span className="muted">(one loop, every ~5 minutes)</span></h2>
        <div className="flow">
          <div className="step"><b>1</b>Market</div><span>→</span>
          <div className="step"><b>2</b>Strategy (AI)</div><span>→</span>
          <div className="step"><b>3</b>Risk</div><span>→</span>
          <div className="step"><b>4</b>Execution</div>
        </div>
        <ul className="list" style={{ marginTop: 14 }}>
          <li><b>Market</b> — live OHLCV + tickers from the first reachable exchange (Binance → Gate.io → HTX → MEXC → WhiteBIT), indicators: SMA, EMA, RSI, MACD, Bollinger, ATR.</li>
          <li><b>Strategy (AI)</b> — an LLM running 100% locally reviews the snapshot + portfolio and decides <i>buy</i> / <i>sell</i> / <i>hold</i> with a confidence score.</li>
          <li><b>Risk</b> — rejects anything that breaks the guardrails: position caps, daily-loss halt, confidence floor.</li>
          <li><b>Execution</b> — fills approved orders on the paper broker and records the trade.</li>
        </ul>
        <p className="muted" style={{ marginTop: 12 }}>
          Paper trading simulation — the AI starts with $10,000 virtual and never touches real money.
        </p>
      </div>

      <div className="panel">
        <h2>Live leaderboard <span className="right muted">public, refreshed automatically</span></h2>
        {board.length === 0 ? (
          <p className="muted">No accounts yet — be the first.</p>
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
                  <td>${u.equity_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                  <td className={u.pnl_pct >= 0 ? "pos" : "neg"}>
                    {u.pnl_pct >= 0 ? "+" : ""}
                    {u.pnl_pct.toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <p className="muted" style={{ marginTop: 18, textAlign: "center" }}>
        API base: <code>{API_URL || "/api (same origin)"}</code> · GitHub:{" "}
        <a href="https://github.com/Mistledan/volvox-trader" target="_blank" rel="noreferrer">
          Mistledan/volvox-trader
        </a>
      </p>
    </div>
  );
}