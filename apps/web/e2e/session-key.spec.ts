import { expect, test, type Page } from "@playwright/test";

// Regression: a staff login stores the key under one sessionStorage name, but /writer sent
// no key at all and /phrasebank read a different name, so production returned 401 /
// "API key required" even for a signed-in admin. Every API client must send the session key.
const baseURL = process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173";
const SESSION_KEY = "e2e-session-key";

test.use({
  baseURL,
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

async function signInAndRecordKeys(page: Page) {
  const keysByPath = new Map<string, Set<string | undefined>>();
  await page.addInitScript((key) => sessionStorage.setItem("aprkb-staff-session", key), SESSION_KEY);
  await page.route("**/v1/**", (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/v1/auth/me") {
      return route.fulfill({ json: { id: "e2e", name: "E2E admin", role: "admin" } });
    }
    const seen = keysByPath.get(path) ?? new Set();
    seen.add(request.headers()["x-api-key"]);
    keysByPath.set(path, seen);
    // The body is irrelevant here; only the request headers are under test.
    return route.fulfill({ status: 500, json: { error: { message: "mocked" } } });
  });
  return keysByPath;
}

function expectEverySentKey(keysByPath: Map<string, Set<string | undefined>>, pathPrefix: string) {
  const matching = [...keysByPath].filter(([path]) => path.startsWith(pathPrefix));
  expect(matching.length, `no request to ${pathPrefix}*`).toBeGreaterThan(0);
  for (const [path, keys] of matching) {
    expect([...keys], `${path} must send the session key`).toEqual([SESSION_KEY]);
  }
}

test("writer sends the signed-in session key", async ({ page }) => {
  const keys = await signInAndRecordKeys(page);
  await page.goto("/writer");
  await expect.poll(() => keys.has("/v1/taxonomy")).toBe(true);
  expectEverySentKey(keys, "/v1/taxonomy");
  expectEverySentKey(keys, "/v1/taxonomy/reference-options");
  expectEverySentKey(keys, "/v1/journals");
});

test("phrasebank sends the signed-in session key", async ({ page }) => {
  const keys = await signInAndRecordKeys(page);
  await page.goto("/phrasebank");
  await expect.poll(() => keys.size).toBeGreaterThan(0);
  expectEverySentKey(keys, "/v1/");
});
