import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { getToken, clearToken } from "./api";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";

function Nav() {
  const authed = !!getToken();
  return (
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
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/dashboard"
          element={
            getToken() ? <Dashboard /> : <Navigate to="/login" replace />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}