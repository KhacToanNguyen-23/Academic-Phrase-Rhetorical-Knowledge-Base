import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export interface AuthenticatedClient {
  id: string;
  name: string;
  role: string;
}

export interface AuthContextValue {
  client: AuthenticatedClient | null;
  apiKey: string | null;
  loading: boolean;
  emailLogin: (email: string, password: string) => Promise<void>;
  login: (credential: string, setupKey?: string) => Promise<void>;
  logout: () => void;
}

const STORAGE_KEY = "aprkb-web-session";
const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchIdentity(apiKey: string): Promise<AuthenticatedClient> {
  const response = await fetch("/v1/auth/session/me", { headers: { "X-API-Key": apiKey } });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Invalid or revoked API key." : "Could not verify this API key.");
  }
  const client = await response.json() as AuthenticatedClient;
  if (client.role !== "curator" && client.role !== "admin") {
    throw new Error("This key does not have staff access. Use a curator or admin key.");
  }
  return client;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState<AuthenticatedClient | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    sessionStorage.removeItem("aprkb-staff-session");
    const savedKey = sessionStorage.getItem(STORAGE_KEY);
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
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    client,
    apiKey,
    loading,
    emailLogin: async (email, password) => {
      const response = await fetch("/v1/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message ?? error.detail ?? "Email sign-in failed.");
      }
      const result = await response.json() as { api_key: string };
      const identity = await fetchIdentity(result.api_key);
      sessionStorage.setItem(STORAGE_KEY, result.api_key);
      setApiKey(result.api_key);
      setClient(identity);
    },
    login: async (credential, setupKey) => {
      const response = await fetch("/v1/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(setupKey ? { "X-API-Key": setupKey.trim() } : {}) },
        body: JSON.stringify({ credential }),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message ?? error.detail ?? "Google sign-in failed.");
      }
      const result = await response.json() as { api_key: string };
      const identity = await fetchIdentity(result.api_key);
      sessionStorage.setItem(STORAGE_KEY, result.api_key);
      setApiKey(result.api_key);
      setClient(identity);
    },
    logout: () => {
      if (apiKey) {
        void fetch("/v1/auth/logout", { method: "POST", headers: { "X-API-Key": apiKey } }).catch(() => undefined);
      }
      sessionStorage.removeItem(STORAGE_KEY);
      setApiKey(null);
      setClient(null);
    },
  }), [apiKey, client, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
