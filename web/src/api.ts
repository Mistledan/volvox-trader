export const API_URL: string = (import.meta.env.VITE_API_URL as string || "").replace(/\/+$/, "");

export function getToken(): string | null {
  return localStorage.getItem("vt_token");
}

export function setToken(token: string): void {
  localStorage.setItem("vt_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("vt_token");
  localStorage.removeItem("vt_user");
}

export function setUserName(name: string): void {
  localStorage.setItem("vt_user", name);
}

export function getUserName(): string {
  return localStorage.getItem("vt_user") ?? "";
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...opts, headers: headers() });
  } catch {
    const where = API_URL || (typeof location !== "undefined" ? location.origin : "the server");
    throw new Error(`Can't reach the trading API at ${where}. Is the backend running? (scripts/api-run.ps1)`);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      detail = j?.detail ?? JSON.stringify(j);
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const fmtUsd = (n: number | null | undefined, dp = 2): string =>
  n == null || Number.isNaN(n) ? "—" : `$${n.toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;

export const fmtPct = (n: number | null | undefined, dp = 2): string =>
  n == null || Number.isNaN(n) ? "—" : `${n >= 0 ? "+" : ""}${n.toFixed(dp)}%`;

export const fmtQty = (n: number | null | undefined): string =>
  n == null || Number.isNaN(n) ? "—" : n.toLocaleString(undefined, { maximumFractionDigits: 6 });

export const fmtTs = (ts: number | null | undefined): string =>
  ts ? new Date(ts * 1000).toLocaleString() : "—";