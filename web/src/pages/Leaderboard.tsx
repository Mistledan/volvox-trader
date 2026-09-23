import { useEffect, useState } from "react";
import { api, fmtPct, fmtUsd } from "../api";
import type { LeaderRow } from "../types";

export default function Leaderboard() {
  const [board, setBoard] = useState<LeaderRow[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const j = await api<{ users: LeaderRow[] }>("/api/v1/leaderboard");
        if (!alive) return;
        setBoard(j.users);
        setErr("");
      } catch (ex) {
        if (alive) setErr(String((ex as Error).message));
      }
    }
    load();
    const t = setInterval(load, 10000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const cls = (n: number) => (n > 0 ? "pos" : n < 0 ? "neg" : "");

  return (
    <>
      <h1 style={{ fontSize: 20 }}>Leaderboard</h1>
      <p className="muted" style={{ marginTop: 2, marginBottom: 14 }}>
        Public standings — live paper-fund equity.
      </p>
      {err && <div className="err" style={{ marginBottom: 12 }}>{err}</div>}
      <div className="panel">
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
                    {u.username}{" "}
                    {u.autopilot ? (
                      <span className="pill p-buy" style={{ marginLeft: 6 }}>AUTOPILOT</span>
                    ) : null}
                  </td>
                  <td className="muted">{u.autopilot ? "on" : "off"}</td>
                  <td className="mono">{fmtUsd(u.equity_usd)}</td>
                  <td className={cls(u.pnl_pct)}>{fmtPct(u.pnl_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}