import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import {
  AuthShell,
  FormError,
  GoogleSignIn,
  OrDivider,
  OrgEmailField,
  PASSWORD_MIN,
  PasswordInput,
  isOrgEmail,
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
  const [submitted, setSubmitted] = useState(false);
  // Email/password registration is restricted to @hyperdatalab.org (Google sign-up is separate).
  const ready = isOrgEmail(email) && password.length >= PASSWORD_MIN && confirm === password;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
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
      <form noValidate onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
        <OrgEmailField
          id="register-email"
          autoComplete="email"
          value={email}
          onChange={setEmail}
          disabled={busy}
          autoFocus
          submitted={submitted}
          hint="Only @hyperdatalab.org addresses can register with email."
        />
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
        <Button type="submit" className="h-10" disabled={busy || !email.trim() || !password || !confirm}>
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </form>
      <OrDivider label="or" />
      <GoogleSignIn text="signup_with" />
    </AuthShell>
  );
}
