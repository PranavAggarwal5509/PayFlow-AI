"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { clearSession, getStoredUser, getToken, saveSession, type SessionUser } from "@/lib/session";
import { authService } from "@/services";

interface AuthState {
  user: SessionUser | null;
  ready: boolean;
  can: (permission: string) => boolean;
  login: (email: string, password: string, remember: boolean) => Promise<SessionUser>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [ready, setReady] = useState(false);

  // Restore the session: optimistically from storage, then confirm with /auth/me.
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setReady(true);
      return;
    }
    setUser(getStoredUser());
    authService
      .me()
      .then((fresh) => setUser(fresh))
      .catch(() => {
        clearSession();
        setUser(null);
      })
      .finally(() => setReady(true));
  }, []);

  // Route guard: everything except /login needs a session.
  useEffect(() => {
    if (!ready) return;
    if (!user && !pathname.startsWith("/login")) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [ready, user, pathname, router]);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const result = await authService.login(email, password, remember);
    saveSession(result.token, result.user, remember);
    setUser(result.user);
    return result.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch {
      // the token may already be invalid; signing out locally is what matters
    }
    clearSession();
    // Full navigation: resets every in-memory cache and polling loop from the previous account.
    window.location.assign("/login?switch=1");
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, ready, login, logout, can: (p: string) => !!user?.permissions.includes(p) }),
    [user, ready, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Renders children only when the signed-in user holds `permission`. */
export function Can({ permission, children, fallback = null }: { permission: string; children: ReactNode; fallback?: ReactNode }) {
  const { can } = useAuth();
  return <>{can(permission) ? children : fallback}</>;
}
