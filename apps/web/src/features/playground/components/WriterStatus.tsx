import type { ReactNode } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <Alert variant="destructive" role="alert">
      <AlertDescription>{error instanceof Error ? error.message : String(error)}</AlertDescription>
    </Alert>
  );
}

export function Notice({ children }: { children: ReactNode }) {
  return (
    <Alert>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}

/** The step the writer is on. Only that step's button is the primary action. */
export type WriterStage = "search" | "build" | "validate" | "copy";
