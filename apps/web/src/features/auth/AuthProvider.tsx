import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export interface AuthenticatedClient {
  id: string;
  name: string;
  role: string;
}

interface AuthContextValue {
  client: AuthenticatedClient | null;
  apiKey: string | null;
  loading: boolean;
  login: (apiKey: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  logout: () => void;
}

const STORAGE_KEY = "aprkb-staff-session";
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState<AuthenticatedClient | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
    login: async (key) => {
      const identity = await fetchIdentity(key.trim());
      sessionStorage.setItem(STORAGE_KEY, key.trim());
      setApiKey(key.trim());
      setClient(identity);
    },
    demoLogin: async () => {
      const response = await fetch("/v1/auth/demo-session", { method: "POST" });
      const result = await response.json() as { api_key?: string; detail?: string };
      if (!response.ok || !result.api_key) {
        throw new Error(result.detail ?? "The local demo is unavailable.");
      }
      const identity = await fetchIdentity(result.api_key);
      sessionStorage.setItem(STORAGE_KEY, result.api_key);
      setApiKey(result.api_key);
      setClient(identity);
    },
    logout: () => {
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
