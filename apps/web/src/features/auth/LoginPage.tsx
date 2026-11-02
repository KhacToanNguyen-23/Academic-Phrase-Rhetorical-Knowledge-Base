import { useState, type FormEvent } from "react";

import { useAuth } from "./AuthProvider";

export function LoginPage() {
  const { login, demoLogin } = useAuth();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(apiKey);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function startDemo() {
    setBusy(true);
    setError("");
    try {
      await demoLogin();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The local demo could not start.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="login-card" aria-labelledby="login-title">
      <p className="eyebrow">Staff access</p>
      <h1 id="login-title">Sign in to Academic Wordbank</h1>
      <p className="lead">Use a curator or admin API key. External writing systems continue to use their own client keys.</p>
      <form className="login-form" onSubmit={submit}>
        <label htmlFor="staff-api-key">Curator or admin API key</label>
        <input
          id="staff-api-key"
          type="password"
          autoComplete="current-password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          required
        />
        {error && <p className="notice notice-warn" role="alert">{error}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy || !apiKey.trim()}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      {import.meta.env.DEV && (
        <button className="btn btn-ghost" type="button" onClick={() => void startDemo()} disabled={busy}>
          {busy ? "Preparing demo…" : "Quick demo"}
        </button>
      )}
    </section>
  );
}
