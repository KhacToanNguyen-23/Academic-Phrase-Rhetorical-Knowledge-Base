import { Link } from "@tanstack/react-router";
import { CircleCheck } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { useAuth } from "./AuthProvider";
import {
  AuthShell,
  FormError,
  GoogleSignIn,
  OrDivider,
  OrgEmailField,
  PasswordInput,
  forgetRegistration,
  isOrgEmail,
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
  const [submitted, setSubmitted] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (!isOrgEmail(email)) return;
    setBusy(true);
    setError("");
    try {
      await emailLogin(email, password);
      forgetRegistration();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Email sign-in failed.");
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
          <CircleCheck strokeWidth={1.5} className="text-emerald-600!" />
          <AlertDescription>Account created. Sign in with the password you just chose.</AlertDescription>
        </Alert>
      )}
      <form noValidate onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
        <OrgEmailField
          id="organization-email"
          autoComplete="username"
          value={email}
          onChange={setEmail}
          disabled={busy}
          autoFocus={!registered}
          submitted={submitted}
        />
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
        <Button type="submit" className="h-10" disabled={busy || !email.trim() || !password}>
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
