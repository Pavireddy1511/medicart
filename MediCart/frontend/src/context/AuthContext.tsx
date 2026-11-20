/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { authApi } from "@/services/api";
import { AUTH_EVENT } from "@/services/http";
import type { Role, TokenResponse, User } from "@/types";
import { session } from "@/utils/storage";

interface AuthContextValue {
  user: User | null;
  initialising: boolean;
  isAuthenticated: boolean;
  hasRole: (...roles: Role[]) => boolean;
  login: (mobile: string, password: string) => Promise<User>;
  register: (data: Parameters<typeof authApi.register>[0]) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(() => session.getUser());
  const [initialising, setInitialising] = useState<boolean>(() => Boolean(session.getAccessToken()));

  useEffect(() => {
    if (!session.getAccessToken()) return;
    let cancelled = false;
    authApi
      .me()
      .then((me) => {
        if (cancelled) return;
        session.setUser(me);
        setUserState(me);
      })
      .catch(() => {
        if (cancelled) return;
        session.clear();
        setUserState(null);
      })
      .finally(() => !cancelled && setInitialising(false));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<{ user: User | null }>).detail;
      setUserState(detail?.user ?? null);
    };
    window.addEventListener(AUTH_EVENT, handler);
    return () => window.removeEventListener(AUTH_EVENT, handler);
  }, []);

  const accept = useCallback((tokens: TokenResponse) => {
    session.save(tokens.access_token, tokens.refresh_token, tokens.user);
    setUserState(tokens.user);
    return tokens.user;
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      initialising,
      isAuthenticated: user !== null,
      hasRole: (...roles) => (user ? roles.includes(user.role) : false),
      login: async (mobile, password) => accept(await authApi.login(mobile, password)),
      register: async (data) => accept(await authApi.register(data)),
      logout: async () => {
        try {
          await authApi.logout();
        } catch {
          /* already signed out server-side or offline; clear locally anyway */
        }
        session.clear();
        setUserState(null);
      },
      setUser: (next) => {
        session.setUser(next);
        setUserState(next);
      },
    }),
    [user, initialising, accept],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function homeFor(role: Role | undefined): string {
  if (role === "admin") return "/admin";
  if (role === "pharmacist") return "/pharmacist";
  return "/";
}
