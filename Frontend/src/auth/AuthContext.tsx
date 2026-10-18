/**
 * Who is signed in, and what they may do.
 *
 * The token and user are held here and mirrored to the API client, so every
 * request carries the token without a call site thinking about it. The token
 * is persisted to localStorage and the user is re-fetched on load, so a reload
 * keeps the session rather than bouncing to the login screen.
 *
 * `can(permission)` is the single gate the UI asks: it is true for the
 * superadmin always, true for an administration user whose role grants the
 * permission, and false otherwise. Components hide what a user cannot do, but
 * the server enforces it regardless — this is for clarity, not security.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  setAuthToken,
  setUnauthorizedHandler,
} from "../api/client";
import { AuthContext, type AuthState } from "./context";
import type { AuthUser } from "../types";

const TOKEN_KEY = "hirewise.token";

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function storeToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // A session that cannot be persisted still works for this tab.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readStoredToken());
  const [user, setUser] = useState<AuthUser | null>(null);
  // Only "loading" when there is a stored token to verify; with none, there is
  // nothing to wait for, so the effect never has to set this synchronously.
  const [loading, setLoading] = useState(() => Boolean(readStoredToken()));

  // Keep the client's token in lockstep with ours.
  useEffect(() => {
    setAuthToken(token);
    storeToken(token);
  }, [token]);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  // A token the server rejects mid-session (expired) logs the user out.
  useEffect(() => {
    setUnauthorizedHandler(signOut);

    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  // On load, if there is a stored token, confirm it still identifies someone.
  useEffect(() => {
    let active = true;

    if (!token) {
      return;
    }

    api
      .me()
      .then((me) => {
        if (active) setUser(me);
      })
      .catch(() => {
        // A stale or invalid token: drop it rather than show a broken session.
        if (active) {
          setToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
    // Only on mount: later token changes come from sign-in, which sets the
    // user directly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);

    // Set the token on the client first, so `refresh` and any immediate call
    // are already authenticated.
    setAuthToken(result.access_token);
    setToken(result.access_token);
    setUser(result.user);
  }, []);

  const register = useCallback(
    async (email: string, password: string, name: string) => {
      const result = await api.register(email, password, name);

      setAuthToken(result.access_token);
      setToken(result.access_token);
      setUser(result.user);
    },
    [],
  );

  const refresh = useCallback(async () => {
    setUser(await api.me());
  }, []);

  const can = useCallback(
    (permission: string) => {
      if (!user) return false;
      if (user.is_superadmin) return true;
      return user.permissions.includes(permission);
    },
    [user],
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      signIn,
      register,
      signOut,
      refresh,
      can,
      isAdministration:
        user?.kind === "administration" || Boolean(user?.is_superadmin),
      isSuperadmin: Boolean(user?.is_superadmin),
    }),
    [user, loading, signIn, register, signOut, refresh, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

