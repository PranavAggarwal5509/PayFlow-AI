/**
 * Browser-side session storage.
 * - "Keep me signed in" → token in localStorage (survives restarts); otherwise sessionStorage.
 * - Saved accounts → only email, name and role (never passwords), for one-click "continue as".
 */

export interface SessionUser {
  id: string;
  email: string;
  name: string;
  role: string;
  role_label: string;
  permissions: string[];
}

export interface SavedAccount {
  email: string;
  name: string;
  role: string;
  role_label: string;
  last_used: number;
}

const TOKEN_KEY = "payflow.token";
const USER_KEY = "payflow.user";
const ACCOUNTS_KEY = "payflow.savedAccounts";

function safe<T>(fn: () => T, fallback: T): T {
  try {
    return fn();
  } catch {
    return fallback;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return safe(() => localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY), null);
}

export function getStoredUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  return safe(() => {
    const raw = localStorage.getItem(USER_KEY) ?? sessionStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  }, null);
}

export function saveSession(token: string, user: SessionUser, remember: boolean): void {
  safe(() => {
    clearSession();
    const store = remember ? localStorage : sessionStorage;
    store.setItem(TOKEN_KEY, token);
    store.setItem(USER_KEY, JSON.stringify(user));
    rememberAccount(user);
  }, undefined);
}

export function clearSession(): void {
  safe(() => {
    [localStorage, sessionStorage].forEach((s) => {
      s.removeItem(TOKEN_KEY);
      s.removeItem(USER_KEY);
    });
  }, undefined);
}

export function getSavedAccounts(): SavedAccount[] {
  if (typeof window === "undefined") return [];
  return safe(() => JSON.parse(localStorage.getItem(ACCOUNTS_KEY) ?? "[]") as SavedAccount[], []).sort(
    (a, b) => b.last_used - a.last_used,
  );
}

function rememberAccount(user: SessionUser): void {
  const others = getSavedAccounts().filter((a) => a.email !== user.email);
  const next: SavedAccount[] = [
    { email: user.email, name: user.name, role: user.role, role_label: user.role_label, last_used: Date.now() },
    ...others,
  ].slice(0, 5);
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(next));
}

export function forgetAccount(email: string): void {
  safe(() => {
    localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(getSavedAccounts().filter((a) => a.email !== email)));
  }, undefined);
}

/** Called by the API layer on 401: drop the session and go to sign-in, remembering where we were. */
export function handleUnauthorized(): void {
  if (typeof window === "undefined") return;
  clearSession();
  if (!window.location.pathname.startsWith("/login")) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.assign(`/login?next=${next}&expired=1`);
  }
}
