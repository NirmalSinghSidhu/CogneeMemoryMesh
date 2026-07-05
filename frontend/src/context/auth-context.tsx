import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  fetchMe,
  getStoredToken,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  type AuthSession,
  type AuthTenant,
  type AuthUser,
} from "@/lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  tenant: AuthTenant | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    name: string,
    workspaceName?: string
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [tenant, setTenant] = useState<AuthTenant | null>(null);
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [loading, setLoading] = useState(true);

  const applySession = useCallback((session: AuthSession) => {
    setToken(session.access_token);
    setUser(session.user);
    setTenant(session.tenant);
  }, []);

  const clearSession = useCallback(() => {
    apiLogout();
    setToken(null);
    setUser(null);
    setTenant(null);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const stored = getStoredToken();
      if (!stored) {
        if (!cancelled) setLoading(false);
        return;
      }

      try {
        const me = await fetchMe();
        if (!cancelled) {
          setUser(me.user);
          setTenant(me.tenant);
          setToken(stored);
        }
      } catch {
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [clearSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await apiLogin(email, password);
      applySession(session);
    },
    [applySession]
  );

  const register = useCallback(
    async (email: string, password: string, name: string, workspaceName?: string) => {
      const session = await apiRegister(email, password, name, workspaceName);
      applySession(session);
    },
    [applySession]
  );

  const logout = useCallback(() => {
    clearSession();
  }, [clearSession]);

  const value = useMemo(
    () => ({
      user,
      tenant,
      token,
      loading,
      isAuthenticated: Boolean(user && token),
      login,
      register,
      logout,
    }),
    [user, tenant, token, loading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
