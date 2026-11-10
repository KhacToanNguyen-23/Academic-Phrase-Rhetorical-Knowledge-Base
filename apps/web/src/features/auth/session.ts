// Single source of truth for the staff API key held in this browser tab.
// AuthProvider writes it on login; every API client must read it through this module
// so a login is never silently ignored by one feature (see the 401 on /writer and the
// "API key required" on /phrasebank that came from clients reading a different key).

export const STAFF_SESSION_KEY = "aprkb-web-session";

// Older builds and the manual key field on the SLR import page store the key here.
// Read it as a fallback only; never write new sessions to it.
const LEGACY_API_KEY = "aprkb-api-key";

export function readApiKey(): string | null {
  return sessionStorage.getItem(STAFF_SESSION_KEY) ?? sessionStorage.getItem(LEGACY_API_KEY);
}

type RequestMiddleware = {
  use(middleware: { onRequest(context: { request: Request }): Request | Promise<Request> }): void;
};

/** Attach the current session key to every request made by an openapi-fetch client. */
export function withSessionApiKey<T extends RequestMiddleware>(client: T): T {
  client.use({
    onRequest({ request }) {
      const key = readApiKey();
      if (key) request.headers.set("X-API-Key", key);
      return request;
    },
  });
  return client;
}
