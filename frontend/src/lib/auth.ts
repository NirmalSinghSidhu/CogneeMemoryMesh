const TOKEN_KEY = "memorymesh_token";

export interface AuthUser {
  id: number;
  email: string;
  name: string;
}

export interface AuthTenant {
  id: number;
  name: string;
  slug: string;
}

export interface AuthSession {
  access_token: string;
  user: AuthUser;
  tenant: AuthTenant;
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getApiBase(): string {
  return import.meta.env.BASE_URL.replace(/\/$/, "");
}

export function authHeaders(): HeadersInit {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const base = getApiBase();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getStoredToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(`${base}${path}`, { ...init, headers });
}

export async function login(email: string, password: string): Promise<AuthSession> {
  const res = await authFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || "Login failed");
  }
  setStoredToken(data.access_token);
  return data;
}

export async function register(
  email: string,
  password: string,
  name: string,
  workspaceName?: string
): Promise<AuthSession> {
  const res = await authFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      name,
      workspace_name: workspaceName || undefined,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || "Registration failed");
  }
  setStoredToken(data.access_token);
  return data;
}

export async function fetchMe(): Promise<{ user: AuthUser; tenant: AuthTenant }> {
  const res = await authFetch("/api/auth/me");
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Session expired");
  }
  return data;
}

export function logout(): void {
  setStoredToken(null);
}
