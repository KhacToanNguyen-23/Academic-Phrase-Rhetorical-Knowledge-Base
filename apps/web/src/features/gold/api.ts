import { createBackendClient } from "@/shared/api/contract-client";

export function goldClient() {
  const client = createBackendClient(import.meta.env.VITE_API_BASE_URL ?? "");
  client.use({
    onRequest({ request }) {
      const key = sessionStorage.getItem("aprkb-api-key");
      if (key) request.headers.set("X-API-Key", key);
      return request;
    },
  });
  return client;
}
