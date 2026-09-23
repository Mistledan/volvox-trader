import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, API_URL, fmtPct, fmtUsd } from "../api";
import type { MarketRow } from "../types";

interface LeaderRow {
  username: string;
  equity_usd: number;
  pnl_pct: number;
  autopilot?: boolean;
}

export default function Landing() {
  const [board, setBoard] = useState<LeaderRow[]>([]);
  const [markets, setMarkets] = useState<MarketRow[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const poll = () => {
      api<{ users: LeaderRow[] }>("/api/v1/leaderboard")
        .then((j) => {
          setBoard(j.users);
          setOnline(true);
        })
        .catch(() => setOnline(false));
      api<{ markets: MarketRow[] }>("/api/v1/markets")
        .then((j) => setMarkets(j.markets))
        .catch(() => {});
    };
    poll();
    const t = setInterval(poll, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="wrap">
      <div className="hero">
        <h1>
          AI trading that never sleeps — <span style={{ color: "var(--blue)" }}>and never blinks</span>
        </h1>
        <p className="sub">
          Volvox Trader is a fully-automated, agent-native paper-trading terminal. An AI reads live
          markets, reasons about them, and trades a virtual $10,000 account — no human in the loop.
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

      <div className="tiles">
        <div className="tile">
          <div className="t">Free $10,000 demo</div>
          <div className="d">Instant virtual funds. The AI trades them for you.</div>
        </div>
        <div className="tile">
          <div className="t">100% autonomous</div>
          <div className="d">Market → strategy → risk → execution, every ~5 minutes.</div>
        </div>
        <div className="tile">
          <div className="t">Trading bots</div>
          <div className="d">Autopilot mode trades 24/7; watch every decision live.</div>
        </div>
        <div className="tile">
          <div className="t">Copy trading</div>
          <div className="d">Mirror the positions of any account on the leaderboard.</div>
        </div>
        <div className="tile">
          <div className="t">Real-time charts</div>
          <div className="d">Live equity history, positions and realized PnL.</div>
        </div>
        <div className="tile">
          <div className="t">Trade anywhere</div>
          <div className="d">Single-port web app served by the API. LAN-ready.</div>
        </div>
      </div>

      {markets.length > 0 && (
        <div className="panel" style={{ marginBottom: 18 }}>
          <h2>
            Live markets <span className="right muted">auto-refreshing</span>
          </h2>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))" }}>
            {markets.map((m) => (
              <div className="card" key={m.symbol}>
                <div className="label">{m.symbol}</div>
                <div className={`value mono ${m.change_pct_24h >= 0 ? "pos" : "neg"}`}>
                  {m.last.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {fmtPct(m.change_pct_24h / 100)} 24h
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="panel" style={{ marginBottom: 18 }}>
        <h2>How the agent thinks <span className="muted">(one loop, every ~5 minutes)</span></h2>
        <div className="flow">
          <div className="step"><b>1</b>Market</div><span>→</span>
          <div className="step"><b>2</b>Strategy (AI)</div><span>→</span>
          <div className="step"><b>3</b>Risk</div><span>→</span>
          <div className="step"><b>4</b>Execution</div>
        </div>
        <ul className="list" style={{ marginTop: 14 }}>
          <li><b>Market</b> — live OHLCV + tickers from the first reachable exchange (Binance → Gate.io → HTX → MEXC → WhiteBIT); indicators: SMA, EMA, RSI, MACD, Bollinger, ATR.</li>
          <li><b>Strategy (AI)</b> — a local LLM reviews the snapshot + portfolio and decides <i>buy</i> / <i>sell</i> / <i>hold</i> with a confidence score.</li>
          <li><b>Risk</b> — rejects anything that breaks guardrails: position caps, daily-loss halt, confidence floor.</li>
          <li><b>Execution</b> — fills approved orders on the paper broker and records the trade.</li>
        </ul>
        <p className="muted" style={{ marginTop: 12 }}>
          Paper trading only — virtual funds, no real money ever touched.
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
                <th>Bot</th>
                <th>Equity</th>
                <th>PnL %</th>
              </tr>
            </thead>
            <tbody>
              {board.map((u, i) => (
                <tr key={`${u.username}-${i}`}>
                  <td>{i + 1}</td>
                  <td>
                    {u.username}
                    {u.autopilot ? <span className="pill p-buy" style={{ marginLeft: 6 }}>ON</span> : null}
                  </td>
                  <td className="muted">{u.autopilot ? "autopilot" : "manual"}</td>
                  <td className="mono">{fmtUsd(u.equity_usd)}</td>
                  <td className={u.pnl_pct >= 0 ? "pos" : "neg"}>{fmtPct(u.pnl_pct)}</td>
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