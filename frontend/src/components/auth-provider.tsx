"use client";

import { createContext, use, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthState =
  | { status: "loading"; user: null }
  | { status: "authenticated"; user: User }
  | { status: "anonymous"; user: null };

type AuthContextValue = AuthState & {
  setUser: (user: User | null) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * Client-side view of the session. The real check happens on the API for every
 * request; this only decides what the header and pages show.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((user) => !cancelled && setState({ status: "authenticated", user }))
      .catch(() => {
        // 401 or a network error. Treating both as anonymous is safe: protected pages
        // make their own request and show their own error or login redirect.
        if (!cancelled) setState({ status: "anonymous", user: null });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setUser = useCallback((user: User | null) => {
    setState(user ? { status: "authenticated", user } : { status: "anonymous", user: null });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setState({ status: "anonymous", user: null });
    }
  }, []);

  const value = useMemo(() => ({ ...state, setUser, logout }), [state, setUser, logout]);
  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth() {
  const context = use(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
