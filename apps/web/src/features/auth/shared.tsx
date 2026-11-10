import { Link } from "@tanstack/react-router";
import { Eye, EyeOff } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { BrandMark } from "@/app/BrandMark";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardFooter, CardHeader } from "@/components/ui/card";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { useAuth } from "./AuthProvider";

/** Client-side mirror of the backend rule: only @hyperdatalab.org mailboxes. */
export const ORG_EMAIL_PATTERN = "[^@\\s]+@[hH][yY][pP][eE][rR][dD][aA][tT][aA][lL][aA][bB]\\.org";
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 128;
/**
 * Hands the just-registered email to the sign-in page without putting it in the URL.
 * In-memory and short-lived, so a remounting route still sees it and a later visit does not.
 */
let registration: { email: string; at: number } | null = null;
export function rememberRegistration(email: string) {
  registration = { email, at: Date.now() };
}
export function recentRegistration(): string {
  return registration && Date.now() - registration.at < 60_000 ? registration.email : "";
}
export function forgetRegistration() {
  registration = null;
}

export async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { error?: { message?: string }; detail?: string };
    return body.error?.message ?? body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

/** Centered brand + card layout shared by sign-in, registration and admin setup. */
export function AuthShell({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="mx-auto flex min-h-svh w-full max-w-md flex-col gap-8 px-6 py-16 sm:pt-24">
      <Link to="/" className="inline-flex items-center gap-2 text-sm font-medium" aria-label="Academic Wordbank home">
        <BrandMark />
        Academic Wordbank
      </Link>
      <main id="main" className="w-full">
        <Card role="region" className="w-full" aria-labelledby="auth-title">
          <CardHeader>
            <h1 id="auth-title" className="text-xl leading-none font-semibold">{title}</h1>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-5">{children}</CardContent>
          {footer && <CardFooter className="justify-center text-sm text-muted-foreground">{footer}</CardFooter>}
        </Card>
      </main>
    </div>
  );
}

export function PasswordInput({
  id,
  value,
  onChange,
  autoComplete,
  disabled,
  invalid,
  describedBy,
  minLength = PASSWORD_MIN,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  disabled?: boolean;
  invalid?: boolean;
  describedBy?: string;
  minLength?: number;
}) {
  const [visible, setVisible] = useState(false);
  const Icon = visible ? EyeOff : Eye;
  return (
    <InputGroup>
      <InputGroupInput
        id={id}
        type={visible ? "text" : "password"}
        required
        minLength={minLength}
        maxLength={PASSWORD_MAX}
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
      />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          onClick={() => setVisible(!visible)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          disabled={disabled}
        >
          <Icon strokeWidth={1.5} />
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}

export function FormError({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <Alert variant="destructive" role="alert" id={id}>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

export function OrDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground" role="separator" aria-label={label}>
      <span className="h-px flex-1 bg-border" />
      {label}
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

type GoogleIdentity = {
  initialize: (options: { client_id: string; nonce: string; callback: (result: { credential: string }) => void }) => void;
  renderButton: (element: HTMLElement, options: { theme: string; size: string; text: string; width?: number }) => void;
};
declare global { interface Window { google?: { accounts: { id: GoogleIdentity } } } }

/**
 * Google Identity Services button. `setupKey` links an admin key on first use;
 * `beforeSignIn` can veto the attempt (e.g. a missing setup key).
 */
export function GoogleSignIn({
  text = "signin_with",
  setupKey,
  beforeSignIn,
}: {
  text?: "signin_with" | "signup_with" | "continue_with";
  setupKey?: string;
  beforeSignIn?: () => string | null;
}) {
  const { login } = useAuth();
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const button = useRef<HTMLDivElement>(null);
  const current = useRef({ login, setupKey, beforeSignIn });
  useEffect(() => { current.current = { login, setupKey, beforeSignIn }; }, [login, setupKey, beforeSignIn]);

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
          client_id: config.client_id,
          nonce: config.nonce,
          callback: ({ credential }) => {
            const state = current.current;
            const veto = state.beforeSignIn?.();
            if (veto) { setError(veto); return; }
            setBusy(true); setError("");
            void state.login(credential, state.setupKey?.trim() || undefined)
              .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Google sign-in failed."))
              .finally(() => setBusy(false));
          },
        });
        window.google.accounts.id.renderButton(button.current, { theme: "outline", size: "large", text });
      } catch (reason) {
        if (!disposed && !controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "Could not load Google sign-in.");
        }
      }
    }
    void initialize();
    return () => { disposed = true; controller.abort(); };
  }, [text]);

  return (
    <div className="flex flex-col items-center gap-3">
      {configured === null && !error && <p role="status" className="text-sm text-muted-foreground">Loading Google sign-in…</p>}
      {configured === false && (
        <p className="text-center text-sm text-muted-foreground">Google sign-in is awaiting administrator configuration.</p>
      )}
      <div ref={button} aria-busy={busy} className={busy ? "pointer-events-none opacity-60" : ""} />
      {busy && <p role="status" className="text-sm">Signing in with Google…</p>}
      {error && <FormError>{error}</FormError>}
    </div>
  );
}
