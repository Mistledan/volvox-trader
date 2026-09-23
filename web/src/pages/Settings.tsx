import { useCallback, useEffect, useState } from "react";
import { api, setToken, fmtTs } from "../api";
import type { Decision, Me } from "../types";

export default function Settings() {
  const [me, setMe] = useState<Me | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [leaderInput, setLeaderInput] = useState("");
  const [cycleOut, setCycleOut] = useState("");

  const load = useCallback(async () => {
    try {
      setMe(await api<Me>("/api/v1/me"));
    } catch (ex) {
      setErr(String((ex as Error).message));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleAutopilot(on: boolean) {
    setBusy(true);
    setErr("");
    setOk("");
    try {
      await api("/api/v1/me/autopilot", { method: "POST", body: JSON.stringify({ enabled: on }) });
      await load();
      setOk(on ? "Autopilot enabled — the bot trades for you now." : "Autopilot paused.");
    } catch (ex) {
      setErr(String((ex as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function setCopy() {
    setBusy(true);
    setErr("");
    setOk("");
    try {
      const body = { leader_username: leaderInput.trim().toLowerCase() || null };
      await api("/api/v1/me/copy", { method: "POST", body: JSON.stringify(body) });
      await load();
      setOk(body.leader_username ? `Now following ${body.leader_username}.` : "Copy trading cleared.");
      setLeaderInput("");
    } catch (ex) {
      setErr(String((ex as Error).message));
    } finally {
      setBusy(false);
    }
  }

  async function runCycle() {
    setBusy(true);
    setErr("");
    setOk("");
    setCycleOut("…thinking");
    try {
      const r = await api<{ decision: Decision; status: string }>("/api/v1/me/cycle", {
        method: "POST",
      });
      setCycleOut(
        `${r.decision.action.toUpperCase()} · ${r.decision.symbol} · ${r.status} · "${r.decision.reasoning}"`
      );
      setOk("Cycle finished.");
      await load();
    } catch (ex) {
      setErr(String((ex as Error).message));
      setCycleOut("");
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    setBusy(true);
    setErr("");
    setOk("");
    try {
      const r = await api<{ token: string }>("/api/v1/auth/refresh", { method: "POST" });
      setToken(r.token);
      setOk("New session token issued and saved.");
    } catch (ex) {
      setErr(String((ex as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 style={{ fontSize: 20 }}>Bot settings</h1>
      <p className="muted" style={{ marginTop: 2, marginBottom: 14 }}>
        Control how your account trades.
      </p>
      {err && <div className="err" style={{ marginBottom: 12 }}>{err}</div>}
      {ok && <div className="ok" style={{ marginBottom: 12 }}>{ok}</div>}

      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))" }}>
        <div className="panel">
          <h2>Autopilot <span className="right">runs every ~5 min</span></h2>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <label className="switch">
              <input
                type="checkbox"
                checked={!!me?.autopilot}
                onChange={(e) => toggleAutopilot(e.target.checked)}
                disabled={busy}
              />
              <span className="slider" />
            </label>
            <div>
              <div>{me?.autopilot ? "ON — AI trades autonomously" : "OFF — manual only"}</div>
              <div className="muted" style={{ fontSize: 12 }}>
                last cycle: {fmtTs(me?.last_cycle_at ?? null)}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Copy trading</h2>
          <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
            Mirror another account's positions on every cycle.
          </p>
          {me?.leader_username && (
            <div className="ok" style={{ marginTop: 0, marginBottom: 8 }}>
              Following <b>{me.leader_username}</b>.{" "}
              <a href="#" onClick={(e) => { e.preventDefault(); setLeaderInput("__clear__"); setCopy(); }}>
                stop
              </a>
            </div>
          )}
          <div style={{ display: "flex", gap: 8 }}>
            <input
              placeholder="leader username"
              value={leaderInput.replace("__clear__", "")}
              onChange={(e) => setLeaderInput(e.target.value)}
              disabled={busy}
            />
            <button className="btn" onClick={setCopy} disabled={busy || !leaderInput.trim()}>
              Follow
            </button>
          </div>
        </div>

        <div className="panel">
          <h2>Manual cycle</h2>
          <button className="btn primary" onClick={runCycle} disabled={busy}>
            Run an AI decision now
          </button>
          {cycleOut && (
            <p className="muted" style={{ marginTop: 8, fontSize: 13 }}>
              {cycleOut}
            </p>
          )}
        </div>

        <div className="panel">
          <h2>Session</h2>
          <button className="btn" onClick={refresh} disabled={busy}>
            Refresh API token
          </button>
          <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            Tokens expire after 7 days; refresh reissues one without re-login.
          </p>
        </div>
      </div>
    </>
  );
}