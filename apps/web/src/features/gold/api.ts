import { withSessionApiKey } from "@/features/auth/session";
import { createBackendClient } from "@/shared/api/contract-client";

export function goldClient() {
  return withSessionApiKey(createBackendClient(import.meta.env.VITE_API_BASE_URL ?? ""));
}
