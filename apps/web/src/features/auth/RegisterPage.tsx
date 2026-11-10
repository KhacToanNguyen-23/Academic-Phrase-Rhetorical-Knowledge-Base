import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  AuthShell,
  FormError,
  GoogleSignIn,
  ORG_EMAIL_PATTERN,
  OrDivider,
  PASSWORD_MIN,
  PasswordInput,
  readError,
  rememberRegistration,
} from "./shared";

/** Self-registration for @hyperdatalab.org staff. It never signs the user in. */
export function RegisterPage({ next }: { next?: string }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [alreadyRegistered, setAlreadyRegistered] = useState(false);
  const [busy, setBusy] = useState(false);

  const tooShort = password.length > 0 && password.length < PASSWORD_MIN;
  const mismatch = confirm.length > 0 && confirm !== password;
  const ready = email.trim() && password.length >= PASSWORD_MIN && confirm === password;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError("");
    setAlreadyRegistered(false);
    try {
      const response = await fetch("/v1/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (!response.ok) {
        setAlreadyRegistered(response.status === 409);
        throw new Error(await readError(response, "Registration failed."));
      }
      rememberRegistration(email.trim().toLowerCase());
      await navigate({ to: "/signin", search: { next }, replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Registration failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      description="Register with your @hyperdatalab.org email to curate Academic Wordbank."
      footer={
        <span>
          Already have an account?{" "}
          <Link to="/signin" search={{ next }} className="font-medium text-foreground underline-offset-4 hover:underline">
            Sign in
          </Link>
        </span>
      }
    >
      <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
        <Field>
          <FieldLabel htmlFor="register-email">Organization email</FieldLabel>
          <Input
            id="register-email"
            type="email"
            autoComplete="email"
            required
            pattern={ORG_EMAIL_PATTERN}
            title="Use your @hyperdatalab.org email address"
            placeholder="you@hyperdatalab.org"
            maxLength={255}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={busy}
            autoFocus
          />
          <FieldDescription>Only @hyperdatalab.org addresses can register.</FieldDescription>
        </Field>
        <Field data-invalid={tooShort || undefined}>
          <FieldLabel htmlFor="register-password">Password</FieldLabel>
          <PasswordInput
            id="register-password"
            autoComplete="new-password"
            value={password}
            onChange={setPassword}
            disabled={busy}
            invalid={tooShort}
            describedBy="register-password-hint"
          />
          <FieldDescription id="register-password-hint" className={tooShort ? "text-destructive" : undefined}>
            At least {PASSWORD_MIN} characters.
          </FieldDescription>
        </Field>
        <Field data-invalid={mismatch || undefined}>
          <FieldLabel htmlFor="register-confirm">Confirm password</FieldLabel>
          <PasswordInput
            id="register-confirm"
            autoComplete="new-password"
            value={confirm}
            onChange={setConfirm}
            disabled={busy}
            invalid={mismatch}
            describedBy={mismatch ? "register-confirm-error" : undefined}
          />
          {mismatch && (
            <FieldDescription id="register-confirm-error" className="text-destructive">
              Passwords do not match.
            </FieldDescription>
          )}
        </Field>
        {error && (
          <FormError>
            {error}
            {alreadyRegistered && (
              <>
                {" "}
                <Link to="/signin" search={{ next }} className="font-medium underline underline-offset-4">Go to sign in</Link>
              </>
            )}
          </FormError>
        )}
        <Button type="submit" disabled={busy || !ready}>
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </form>
      <OrDivider label="or" />
      <GoogleSignIn text="signup_with" />
    </AuthShell>
  );
}
