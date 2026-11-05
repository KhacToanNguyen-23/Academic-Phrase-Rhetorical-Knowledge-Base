import { Link } from "@tanstack/react-router";

import { BrandMark } from "@/app/BrandMark";
import { LoginPage } from "./LoginPage";

/** Standalone sign-in screen. Redirecting after a successful sign-in is done by the route's beforeLoad. */
export function SigninPage() {
  return (
    <div className="mx-auto flex min-h-svh w-full max-w-md flex-col gap-8 px-6 pt-24">
      <Link to="/" className="inline-flex items-center gap-2 text-sm font-medium" aria-label="Academic Wordbank home">
        <BrandMark />
        Academic Wordbank
      </Link>
      <main id="main" className="w-full">
        <LoginPage />
      </main>
    </div>
  );
}
