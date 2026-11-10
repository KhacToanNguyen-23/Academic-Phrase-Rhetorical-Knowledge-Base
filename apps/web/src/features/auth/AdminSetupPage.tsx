import { Link } from "@tanstack/react-router";
import { useCallback, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useAuth } from "./AuthProvider";
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
} from "./shared";

/** One-time link of a bootstrap admin API key to an email/password or Google account. */
export function AdminSetupPage() {
  const { emailLogin } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const requireKey = useCallback(() => (apiKey.trim() ? null : "Enter the admin setup key first."), [apiKey]);

  const [submitted, setSubmitted] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (!isOrgEmail(email)) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/v1/auth/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": apiKey.trim() },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (!response.ok) throw new Error(await readError(response, "Admin setup failed."));
      await emailLogin(email, password);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Admin setup failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="First-time admin setup"
      description="Link the bootstrap admin API key to your email or Google account once. Later sign-ins do not need the key."
      footer={<Link to="/signin" className="font-medium text-foreground underline-offset-4 hover:underline">Back to sign in</Link>}
    >
      <form noValidate onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
        <Field>
          <FieldLabel htmlFor="admin-setup-key">Admin API key</FieldLabel>
          <Input id="admin-setup-key" type="password" autoComplete="off" required value={apiKey}
            onChange={(event) => setApiKey(event.target.value)} disabled={busy} autoFocus />
          <FieldDescription>Created with <code>make bootstrap-key</code>.</FieldDescription>
        </Field>
        <OrgEmailField id="admin-setup-email" autoComplete="email" value={email} onChange={setEmail}
          disabled={busy} submitted={submitted} />
        <Field>
          <FieldLabel htmlFor="admin-setup-password">Password</FieldLabel>
          <PasswordInput id="admin-setup-password" autoComplete="new-password" value={password}
            onChange={setPassword} disabled={busy} describedBy="admin-setup-password-hint" />
          <FieldDescription id="admin-setup-password-hint">At least {PASSWORD_MIN} characters.</FieldDescription>
        </Field>
        {error && <FormError>{error}</FormError>}
        <Button type="submit" className="h-10" disabled={busy || !apiKey.trim() || !email.trim() || password.length < PASSWORD_MIN}>
          {busy ? "Linking…" : "Link admin key and sign in"}
        </Button>
      </form>
      <OrDivider label="or link with Google" />
      <GoogleSignIn text="continue_with" setupKey={apiKey} beforeSignIn={requireKey} />
    </AuthShell>
  );
}
