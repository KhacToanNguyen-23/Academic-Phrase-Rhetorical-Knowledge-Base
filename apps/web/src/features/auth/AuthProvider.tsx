import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { STAFF_SESSION_KEY } from "./session";

export interface AuthenticatedClient {
  id: string;
  name: string;
  role: string;
}

export interface AuthContextValue {
  client: AuthenticatedClient | null;
  apiKey: string | null;
  loading: boolean;
  login: (apiKey: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  logout: () => void;
}

const STORAGE_KEY = STAFF_SESSION_KEY;
const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchIdentity(apiKey: string): Promise<AuthenticatedClient> {
  const response = await fetch("/v1/auth/me", { headers: { "X-API-Key": apiKey } });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Invalid or revoked API key." : "Could not verify this API key.");
  }
  const client = await response.json() as AuthenticatedClient;
  if (client.role !== "curator" && client.role !== "admin") {
    throw new Error("This key does not have staff access. Use a curator or admin key.");
  }
  return client;
}

const requestDemoSession = import.meta.env.DEV || import.meta.env.MODE === "inspect"
  ? async (): Promise<{ apiKey: string; identity: AuthenticatedClient }> => {
      const response = await fetch("/v1/auth/demo-session", { method: "POST" });
      const result = await response.json() as { api_key?: string; detail?: string };
      if (!response.ok || !result.api_key) {
        throw new Error(result.detail ?? "The local demo is unavailable.");
      }
      return { apiKey: result.api_key, identity: await fetchIdentity(result.api_key) };
    }
  : async (): Promise<{ apiKey: string; identity: AuthenticatedClient }> => {
      throw new Error("The local demo is available only in development and inspect builds.");
    };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState<AuthenticatedClient | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const inspectAutoLoginStarted = useRef(false);
  const demoLogin = useCallback(async () => {
    const session = await requestDemoSession();
    sessionStorage.setItem(STORAGE_KEY, session.apiKey);
    setApiKey(session.apiKey);
    setClient(session.identity);
  }, []);

  useEffect(() => {
    const savedKey = sessionStorage.getItem(STORAGE_KEY);
    if (!savedKey && import.meta.env.MODE === "inspect" && import.meta.env.VITE_INSPECT_AUTOLOGIN === "1") {
      if (inspectAutoLoginStarted.current) return;
      inspectAutoLoginStarted.current = true;
      void demoLogin()
        .catch(() => sessionStorage.removeItem(STORAGE_KEY))
        .finally(() => setLoading(false));
      return;
    }
    if (!savedKey) {
      setLoading(false);
      return;
    }
    void fetchIdentity(savedKey)
      .then((identity) => {
        setApiKey(savedKey);
        setClient(identity);
      })
      .catch(() => sessionStorage.removeItem(STORAGE_KEY))
      .finally(() => setLoading(false));
  }, [demoLogin]);

  const value = useMemo<AuthContextValue>(() => ({
    client,
    apiKey,
    loading,
    login: async (key) => {
      const identity = await fetchIdentity(key.trim());
      sessionStorage.setItem(STORAGE_KEY, key.trim());
      setApiKey(key.trim());
      setClient(identity);
    },
    demoLogin,
    logout: () => {
      sessionStorage.removeItem(STORAGE_KEY);
      setApiKey(null);
      setClient(null);
    },
  }), [apiKey, client, demoLogin, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
