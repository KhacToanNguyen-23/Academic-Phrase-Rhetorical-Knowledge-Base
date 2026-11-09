import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "./AuthProvider";

type GoogleIdentity = {
  initialize: (options: { client_id: string; nonce: string; callback: (result: { credential: string }) => void }) => void;
  renderButton: (element: HTMLElement, options: { theme: string; size: string; text: string }) => void;
};
declare global { interface Window { google?: { accounts: { id: GoogleIdentity } } } }

export function LoginPage() {
  const { login, emailLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [register, setRegister] = useState(false);
  const [notice, setNotice] = useState("");
  const [setup, setSetup] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const button = useRef<HTMLDivElement>(null);
  const current = useRef({ login, apiKey, setup });
  useEffect(() => { current.current = { login, apiKey, setup }; }, [login, apiKey, setup]);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    async function initialize() {
      try {
        const response = await fetch("/v1/auth/google/config", { signal: controller.signal });
        if (!response.ok) throw new Error("Could not load Google sign-in.");
        const config = await response.json() as { client_id: string | null; nonce: string };
        if (disposed) return;
        setConfigured(Boolean(config.client_id));
        if (!config.client_id) return;
        if (!window.google?.accounts.id) {
          await new Promise<void>((resolve, reject) => {
            let script = document.querySelector<HTMLScriptElement>('script[src="https://accounts.google.com/gsi/client"]');
            if (!script) {
              script = document.createElement("script");
              script.src = "https://accounts.google.com/gsi/client";
              script.async = true;
              document.head.appendChild(script);
            }
            script.addEventListener("load", () => resolve(), { once: true });
            script.addEventListener("error", () => reject(new Error("Google sign-in could not load. Reload to try again.")), { once: true });
          });
        }
        if (disposed || !button.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: config.client_id, nonce: config.nonce,
          callback: ({ credential }) => {
            const state = current.current;
            if (state.setup && !state.apiKey.trim()) { setError("Enter the admin setup key first."); return; }
            setBusy(true); setError("");
            void state.login(credential, state.setup ? state.apiKey : undefined)
              .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Sign-in failed."))
              .finally(() => setBusy(false));
          },
        });
        window.google.accounts.id.renderButton(button.current, { theme: "outline", size: "large", text: "signin_with" });
      } catch (reason) {
        if (!disposed) setError(reason instanceof Error ? reason.message : "Could not load Google sign-in.");
      }
    }
    void initialize();
    return () => { disposed = true; controller.abort(); };
  }, []);

  async function submitEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      if (setup) {
        const response = await fetch("/v1/auth/setup", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-API-Key": apiKey.trim() },
          body: JSON.stringify({ email: email.trim(), password }),
        });
        if (!response.ok) {
          const result = await response.json();
          throw new Error(result.error?.message ?? result.detail ?? "Admin setup failed.");
        }
        await emailLogin(email, password);
      } else if (register) {
        const response = await fetch("/v1/auth/register", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: email.trim(), password }),
        });
        if (!response.ok) {
          const result = await response.json();
          throw new Error(result.error?.message ?? result.detail ?? "Registration failed.");
        }
        setRegister(false);
        setPassword("");
        setNotice("Email registered. Enter your password to sign in.");
      } else {
        await emailLogin(email, password);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Email sign-in failed.");
    } finally { setBusy(false); }
  }

  return (
    <Card role="region" className="w-full" aria-labelledby="login-title">
      <CardHeader>
        <h1 id="login-title" className="text-xl leading-none font-semibold">Sign in to Academic Wordbank</h1>
        <CardDescription>Use your @hyperdatalab.org email and password, or any Google account.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form onSubmit={(event) => void submitEmail(event)} className="flex flex-col gap-4">
          <Field>
            <FieldLabel htmlFor="organization-email">Organization email</FieldLabel>
            <Input id="organization-email" type="email" autoComplete="email" required
              pattern="[^@]+@[hH][yY][pP][eE][rR][dD][aA][tT][aA][lL][aA][bB]\.org"
              placeholder="you@hyperdatalab.org" maxLength={255} value={email}
              onChange={(event) => setEmail(event.target.value)} disabled={busy} />
          </Field>
          <Field>
            <FieldLabel htmlFor="organization-password">Password</FieldLabel>
            <Input id="organization-password" type="password" required minLength={8} maxLength={128}
              autoComplete={register || setup ? "new-password" : "current-password"} value={password}
              onChange={(event) => setPassword(event.target.value)} disabled={busy} />
            {(register || setup) && <p className="text-sm text-muted-foreground">Use at least 8 characters.</p>}
          </Field>
          {setup && <Field>
            <FieldLabel htmlFor="admin-setup-key">Admin API key (first-time setup only)</FieldLabel>
            <Input id="admin-setup-key" type="password" autoComplete="off" required value={apiKey} onChange={(e) => setApiKey(e.target.value)} disabled={busy} />
            <p className="text-sm text-muted-foreground">Link your admin key to your email or Google account once. Future sign-ins do not need the key.</p>
          </Field>}
          <Button type="submit" disabled={busy || !email.trim() || !password || (setup && !apiKey.trim())}>
            {busy ? "Please wait…" : setup ? "Link admin key and sign in" : register ? "Register email" : "Sign in with email"}
          </Button>
          {!setup && <Button type="button" variant="link" disabled={busy}
            onClick={() => { setRegister(!register); setPassword(""); setError(""); setNotice(""); }}>
            {register ? "Already registered? Sign in" : "New email? Register"}
          </Button>}
        </form>
        {notice && <p role="status" className="text-sm">{notice}</p>}
        <div className="text-center text-sm text-muted-foreground">Or sign in with Google</div>
        {configured === null && !error && <p role="status">Loading Google sign-in…</p>}
        {configured === false && <Alert><AlertDescription>Google sign-in is awaiting administrator configuration.</AlertDescription></Alert>}
        <div ref={button} aria-busy={busy} className={busy ? "pointer-events-none opacity-60" : ""} />
        {busy && <p role="status">Signing in…</p>}
        {error && <Alert variant="destructive" role="alert"><AlertDescription>{error}</AlertDescription></Alert>}
        <Button type="button" variant="link" onClick={() => { setSetup(!setup); setRegister(false); setPassword(""); setApiKey(""); setError(""); setNotice(""); }}>
          {setup ? "Back to sign-in" : "First-time admin setup"}
        </Button>
      </CardContent>
    </Card>
  );
}
