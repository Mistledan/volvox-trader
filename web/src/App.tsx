import { BrowserRouter, Routes, Route, Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { getToken, clearToken, getUserName } from "./api";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Markets from "./pages/Markets";
import Signals from "./pages/Signals";
import Leaderboard from "./pages/Leaderboard";
import Settings from "./pages/Settings";

const TABS = [
  { to: "/dashboard", label: "Dashboard", ic: "◈" },
  { to: "/markets", label: "Markets", ic: "▦" },
  { to: "/signals", label: "Signals", ic: "⚡" },
  { to: "/leaderboard", label: "Leaderboard", ic: "≡" },
  { to: "/settings", label: "Bot settings", ic: "⚙" },
];

function PublicLayout() {
  const authed = !!getToken();
  return (
    <>
      <header className="nav">
        <div className="nav-brand">
          <NavLink to="/">Volvox Trader</NavLink>
        </div>
        <nav className="nav-links">
          {!authed ? (
            <>
              <NavLink to="/login">Log in</NavLink>
              <NavLink to="/register" className="btn primary">
                Create account
              </NavLink>
            </>
          ) : (
            <>
              <NavLink to="/dashboard">Dashboard</NavLink>
              <a
                href="/"
                onClick={() => {
                  clearToken();
                }}
              >
                Log out
              </a>
            </>
          )}
        </nav>
      </header>
      <Outlet />
    </>
  );
}

function Terminal() {
  const loc = useLocation();
  const username = getUserName();
  return (
    <div className="term">
      <aside className="term-side">
        <div className="brand">
          Volvox Trader <small>paper trading terminal</small>
        </div>
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={loc.pathname === t.to ? "term-item active" : "term-item"}
          >
            <span className="ic">{t.ic}</span>
            {t.label}
          </NavLink>
        ))}
        <div className="spacer" />
        <div className="term-user">
          <a
            href="/"
            onClick={() => {
              clearToken();
            }}
          >
            Log out
          </a>
          <div className="name">{username || "trader"}</div>
          <a href="/dashboard" className="muted" style={{ fontSize: 11 }}>
            100% paper · $10,000 demo
          </a>
        </div>
      </aside>
      <main className="term-main">
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/markets" element={<Markets />} />
          <Route path="/signals" element={<Signals />} />
          <Route path="/leaderboard" element={<Leaderboard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function Guard({ children }: { children: React.ReactNode }) {
  return getToken() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>
        <Route
          path="/dashboard"
          element={
            <Guard>
              <Terminal />
            </Guard>
          }
        />
        <Route
          path="/markets"
          element={
            <Guard>
              <Terminal />
            </Guard>
          }
        />
        <Route
          path="/signals"
          element={
            <Guard>
              <Terminal />
            </Guard>
          }
        />
        <Route
          path="/leaderboard"
          element={
            <Guard>
              <Terminal />
            </Guard>
          }
        />
        <Route
          path="/settings"
          element={
            <Guard>
              <Terminal />
            </Guard>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}