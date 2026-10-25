import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { login as loginRequest, register as registerRequest } from "../api/client";

const SESSION_KEY = "khusela.session.v1";
const AuthContext = createContext(null);

function readSession() {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(readSession);

  const persist = useCallback((next) => {
    if (next) {
      window.localStorage.setItem(SESSION_KEY, JSON.stringify(next));
    } else {
      window.localStorage.removeItem(SESSION_KEY);
    }
    setSession(next);
  }, []);

  const signIn = useCallback(
    async (token) => {
      const next = await loginRequest(token);
      persist(next);
      return next;
    },
    [persist],
  );

  const signUp = useCallback(
    async (businessName, password) => {
      const next = await registerRequest({ businessName, password });
      persist(next);
      return next;
    },
    [persist],
  );

  const signOut = useCallback(() => persist(null), [persist]);

  const value = useMemo(
    () => ({ session, signIn, signUp, signOut }),
    [session, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
