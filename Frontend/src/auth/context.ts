import { createContext, useContext } from "react";
import type { AuthUser } from "../types";

export interface AuthState {
  user: AuthUser | null;
  /** True until the initial "who am I" check settles. */
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  signOut: () => void;
  /** Re-read the current user, after a role or profile change. */
  refresh: () => Promise<void>;
  can: (permission: string) => boolean;
  isAdministration: boolean;
  isSuperadmin: boolean;
}

export const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
