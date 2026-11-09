import { expect, type APIRequestContext, type Page } from "@playwright/test";

let accountSequence = 0;

export async function authenticateCurator(page: Page, request: APIRequestContext) {
  const email = `e2e-${Date.now()}-${accountSequence++}@hyperdatalab.org`;
  const password = "e2e-password-123";
  const registration = await request.post("/v1/auth/register", { data: { email, password } });
  expect(registration.status(), "register an isolated e2e curator").toBe(201);
  const response = await request.post("/v1/auth/login", { data: { email, password } });
  expect(response.ok(), "sign in with the isolated e2e curator").toBeTruthy();
  const session = await response.json() as { api_key: string };
  await page.addInitScript((key: string) => sessionStorage.setItem("aprkb-web-session", key), session.api_key);
  return session.api_key;
}
