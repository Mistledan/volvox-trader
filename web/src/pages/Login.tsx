import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, setToken } from "../api";

export default function Login() {
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
      const r = await api<{ token: string }>("/api/v1/auth/login", {
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
        <h1 style={{ marginBottom: 8 }}>Log in</h1>
        <p className="muted">Watch your AI trade the paper markets.</p>
        <form onSubmit={submit}>
          <label htmlFor="username">Username</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
          {err && <div className="err">{err}</div>}
          <div style={{ marginTop: 20 }}>
            <button className="btn primary" disabled={busy}>
              {busy ? "Signing in…" : "Log in"}
            </button>
          </div>
        </form>
        <p className="muted" style={{ marginTop: 16 }}>
          No account? <Link to="/register">Create one — free, paper trading.</Link>
        </p>
      </div>
    </div>
  );
}