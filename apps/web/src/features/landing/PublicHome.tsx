import { Link } from "@tanstack/react-router";

import { BrandMark } from "@/app/BrandMark";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthProvider";

// TODO(owner): placeholder for the public landing page. Phase 04 replaces this file.
export function PublicHome() {
  const { client } = useAuth();
  return (
    <main id="main" className="mx-auto flex min-h-svh w-full max-w-3xl flex-col justify-center gap-6 px-6 py-16">
      <BrandMark className="size-8" />
      <h1 className="text-4xl font-semibold tracking-tight text-balance">The right phrasing for every claim</h1>
      <p className="max-w-xl text-base leading-7 text-muted-foreground">
        Academic Wordbank is a phrasebank and academic vocabulary dictionary, built from licensed journal articles.
      </p>
      <div className="flex flex-wrap gap-2">
        {client ? (
          <Button asChild>
            <Link to="/app">Open the workspace</Link>
          </Button>
        ) : (
          <Button asChild>
            <Link to="/signin">Staff sign in</Link>
          </Button>
        )}
        <Button asChild variant="secondary">
          <Link to="/writer">Open the writer</Link>
        </Button>
      </div>
    </main>
  );
}
