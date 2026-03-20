"use client";

/**
 * AuthProvider wraps the app and:
 * 1. Calls initAuth() on mount to perform silent Keycloak SSO check.
 * 2. Stores auth state in a Zustand-like React context.
 * 3. Sets/clears the "kc_auth" and "kc_role" cookies used by middleware.ts.
 */

import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { initAuth, login, logout, type AuthState } from "@/lib/auth";

const defaultState: AuthState = { authenticated: false, token: null, user: null };

const AuthContext = createContext<{
  auth: AuthState;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
}>({
  auth: defaultState,
  login: async () => {},
  logout: async () => {},
  isLoading: true,
});

function setCookie(name: string, value: string, days = 1) {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${value}; path=/; max-age=${days * 86400}; SameSite=Lax`;
}
function deleteCookie(name: string) {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; path=/; max-age=0`;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(defaultState);
  const [isLoading, setIsLoading] = useState(true);

  const applyAuthState = (state: AuthState) => {
    setAuth(state);
    if (state.authenticated) {
      setCookie("kc_auth", "1");
      setCookie("kc_role", state.user?.roles.join(",") ?? "");
    } else {
      deleteCookie("kc_auth");
      deleteCookie("kc_role");
    }
  };

  useEffect(() => {
    initAuth()
      .then(applyAuthState)
      .finally(() => setIsLoading(false));
  }, []);

  const handleLogin = useCallback(async () => {
    await login();
  }, []);

  const handleLogout = useCallback(async () => {
    applyAuthState(defaultState);
    await logout();
  }, []);

  return (
    <AuthContext.Provider value={{ auth, login: handleLogin, logout: handleLogout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
