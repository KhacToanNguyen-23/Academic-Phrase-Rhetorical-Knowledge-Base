import createClient from "openapi-fetch";
import type { paths } from "./schema";

/** Create a client whose request and response types come from the backend OpenAPI contract. */
export function createBackendClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}
