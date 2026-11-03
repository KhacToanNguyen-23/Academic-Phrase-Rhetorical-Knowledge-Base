import { Link } from "@tanstack/react-router";

import { BrandMark } from "@/app/BrandMark";
import { LoginPage } from "./LoginPage";

/** Standalone sign-in screen. Redirecting after a successful sign-in is done by the route's beforeLoad. */
export function SigninPage() {
  return (
    <div className="mx-auto min-h-svh w-full max-w-3xl px-6 py-6">
      <Link to="/" className="inline-flex items-center gap-2 text-sm font-medium" aria-label="Academic Wordbank home">
        <BrandMark />
        Academic Wordbank
      </Link>
      <main id="main">
        <LoginPage />
      </main>
    </div>
  );
}
