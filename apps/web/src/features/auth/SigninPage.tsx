import { Link } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "./AuthProvider";
import {
  AuthShell,
  FormError,
  GoogleSignIn,
  ORG_EMAIL_PATTERN,
  OrDivider,
  PasswordInput,
  forgetRegistration,
  recentRegistration,
} from "./shared";

/** Sign-in only. Redirecting after a successful sign-in is done by the route's beforeLoad. */
export function SigninPage({ next }: { next?: string }) {
  const { emailLogin } = useAuth();
  const [registered] = useState(recentRegistration);
  const [email, setEmail] = useState(registered);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await emailLogin(email, password);
      forgetRegistration();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Email sign-in failed.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Sign in to Academic Wordbank"
      description="Welcome back. Sign in with your @hyperdatalab.org email."
      footer={
        <span>
          New to Academic Wordbank?{" "}
          <Link to="/register" search={{ next }} className="font-medium text-foreground underline-offset-4 hover:underline">
            Create an account
          </Link>
        </span>
      }
    >
      {registered && (
        <Alert role="status">
          <AlertDescription>Account created. Sign in with the password you just chose.</AlertDescription>
        </Alert>
      )}
      <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
        <Field>
          <FieldLabel htmlFor="organization-email">Organization email</FieldLabel>
          <Input
            id="organization-email"
            type="email"
            autoComplete="username"
            required
            pattern={ORG_EMAIL_PATTERN}
            title="Use your @hyperdatalab.org email address"
            placeholder="you@hyperdatalab.org"
            maxLength={255}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={busy}
            autoFocus={!registered}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="organization-password">Password</FieldLabel>
          <PasswordInput
            id="organization-password"
            autoComplete="current-password"
            value={password}
            onChange={setPassword}
            disabled={busy}
            invalid={Boolean(error)}
            describedBy={error ? "signin-error" : undefined}
            minLength={1}
          />
        </Field>
        {error && <FormError id="signin-error">{error}</FormError>}
        <Button type="submit" disabled={busy || !email.trim() || !password}>
          {busy ? "Signing in…" : "Sign in with email"}
        </Button>
      </form>
      <OrDivider label="or" />
      <GoogleSignIn text="signin_with" />
      <p className="text-center text-xs text-muted-foreground">
        Administrator with a setup key?{" "}
        <Link to="/setup" className="underline underline-offset-4">First-time admin setup</Link>
      </p>
    </AuthShell>
  );
}
