import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, setToken } from "../api";

export default function Register() {
  const nav = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r = await api<{ token: string }>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(r.token);
      nav("/dashboard");
    } catch (ex) {
      setErr(String((ex as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap narrow">
      <div className="form-wrap">
        <h1 style={{ marginBottom: 8 }}>Create your free paper account</h1>
        <p className="muted">
          You get a $10,000 simulated portfolio and your own AI agent. No real money,
          no card needed.
        </p>
        <form onSubmit={submit}>
          <label htmlFor="reg-username">Username (3–32 chars)</label>
          <input
            id="reg-username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <label htmlFor="reg-password">Password (6+ chars)</label>
          <input
            id="reg-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
          {err && <div className="err">{err}</div>}
          <div style={{ marginTop: 20 }}>
            <button className="btn primary" disabled={busy}>
              {busy ? "Creating…" : "Create account"}
            </button>
          </div>
        </form>
        <p className="muted" style={{ marginTop: 16 }}>
          Already have one? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}