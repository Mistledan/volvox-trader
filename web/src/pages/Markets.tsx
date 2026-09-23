import { useEffect, useRef, useState } from "react";
import { api, fmtPct } from "../api";
import type { MarketRow } from "../types";

export default function Markets() {
  const [rows, setRows] = useState<MarketRow[]>([]);
  const [updated, setUpdated] = useState("");
  const [err, setErr] = useState("");
  const [flash, setFlash] = useState<Record<string, string>>({});
  const prev = useRef<Record<string, number>>({});

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const j = await api<{ markets: MarketRow[]; updated_at: string }>("/api/v1/markets");
        if (!alive) return;
        setRows(j.markets);
        setUpdated(j.updated_at);
        setErr("");
        const f: Record<string, string> = {};
        for (const m of j.markets) {
          const old = prev.current[m.symbol];
          if (old != null && m.last !== old) f[m.symbol] = m.last > old ? "up" : "down";
        }
        setFlash(f);
        setTimeout(() => setFlash({}), 800);
        prev.current = Object.fromEntries(j.markets.map((m) => [m.symbol, m.last]));
      } catch (ex) {
        if (alive) setErr(String((ex as Error).message));
      }
    }
    load();
    const t = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <>
      <h1 style={{ fontSize: 20 }}>Live markets</h1>
      <p className="muted" style={{ marginTop: 2, marginBottom: 14 }}>
        {updated ? `feed updated ${updated}` : "connecting to live feed…"}
      </p>
      {err && (
        <div className="err" style={{ marginBottom: 12 }}>
          {err} — showing cached/last-known prices if any.
        </div>
      )}
      {rows.length === 0 ? (
        <div className="panel muted">No market feed right now. The API retries automatically.</div>
      ) : (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(240px,1fr))" }}>
          {rows.map((m) => (
            <div className="card" key={m.symbol}>
              <div className="label" style={{ display: "flex", justifyContent: "space-between" }}>
                <span>{m.symbol}</span>
                <span className={m.change_pct_24h >= 0 ? "pos" : "neg"}>{fmtPct(m.change_pct_24h / 100, 2)}</span>
              </div>
              <div className={`value mono ${flash[m.symbol] === "up" ? "pos" : flash[m.symbol] === "down" ? "neg" : ""}`}>
                {m.last.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
                H {m.high_24h.toLocaleString(undefined, { maximumFractionDigits: 2 })} · L{" "}
                {m.low_24h.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}