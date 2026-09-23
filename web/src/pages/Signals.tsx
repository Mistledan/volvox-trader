import { useEffect, useState } from "react";
import { api, fmtPct } from "../api";
import type { SignalRow } from "../types";

function pill(action: string): string {
  const a = action.toLowerCase();
  return a === "buy" ? "p-buy" : a === "sell" ? "p-sell" : "p-hold";
}

export default function Signals() {
  const [rows, setRows] = useState<SignalRow[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const j = await api<{ signals: SignalRow[] }>("/api/v1/signals");
        if (!alive) return;
        setRows(j.signals);
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

  return (
    <>
      <h1 style={{ fontSize: 20 }}>Signals feed</h1>
      <p className="muted" style={{ marginTop: 2, marginBottom: 14 }}>
        Latest AI decisions across every account. Public — no login needed.
      </p>
      {err && <div className="err" style={{ marginBottom: 12 }}>{err}</div>}
      {rows.length === 0 ? (
        <div className="panel muted">No signals yet. Start an autopilot and decisions will appear here.</div>
      ) : (
        <div className="feed">
          {rows.map((s, i) => (
            <div className="feed-item" key={i}>
              <div className="who">
                <div className="u">{s.username}</div>
                <div className="t">{new Date(s.time * 1000).toLocaleString()}</div>
              </div>
              <div className="body">
                <span className={`pill ${pill(s.action)}`} style={{ marginRight: 8 }}>
                  {s.action.toUpperCase()}
                </span>
                {s.symbol}
                <span className="meta" style={{ marginLeft: 8 }}>
                  conf {fmtPct(s.confidence * 100, 0)}
                </span>
                <div className="muted" style={{ marginTop: 4 }}>{s.reasoning}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}