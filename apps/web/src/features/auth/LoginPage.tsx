import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
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
    <Card role="region" className="w-full" aria-labelledby="login-title">
      <CardHeader>
        <h1 id="login-title" className="text-xl leading-none font-semibold">
          Sign in to Academic Wordbank
        </h1>
        <CardDescription>
          Use a curator or admin API key. Ask an administrator if you do not have one. External writing systems keep
          using their own client keys.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit}>
          <FieldGroup>
            <Field data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor="staff-api-key">Curator or admin API key</FieldLabel>
              <Input
                id="staff-api-key"
                type="password"
                autoComplete="current-password"
                value={apiKey}
                onChange={(event) => setApiKey(event.target.value)}
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? "login-error" : undefined}
                required
              />
            </Field>
            {error && (
              <Alert variant="destructive" id="login-error" role="alert">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" disabled={busy || !apiKey.trim()}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
            {import.meta.env.DEV && (
              <Button type="button" variant="secondary" onClick={() => void startDemo()} disabled={busy}>
                {busy ? "Preparing demo…" : "Quick demo"}
              </Button>
            )}
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
