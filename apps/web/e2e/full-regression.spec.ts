import { expect, test, type Page, type APIRequestContext } from "@playwright/test";

test.skip(process.env.ONLINE_RANKING_LIVE !== "1", "Requires isolated seeded live API");

const screens = [
  ["/app", "Workspace"], ["/library", "Pattern library"],
  ["/phrasebank", "Phrasebank"], ["/vocabulary", "Academic vocabulary"],
  ["/journals", "Journal profiles"], ["/inbox", "Inbox"],
  ["/gold", "Gold review"], ["/extract", "Phrase extraction"],
  ["/import", "SLR import"],
  ["/playground", "Playground"],
  ["/admin", "Administration"],
] as const;

async function staff(page: Page, request: APIRequestContext) {
  const response = await request.post("/v1/auth/demo-session");
  expect(response.ok()).toBeTruthy();
  const session = await response.json();
  expect(typeof session.api_key).toBe("string");
  await page.addInitScript((key: string) => sessionStorage.setItem("aprkb-staff-session", key), session.api_key);
}

function errorsOn(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

for (const [path, heading] of screens) {
  test(`FULL-NAV guest is guarded: ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page).toHaveURL(/\/signin\?next=/);
    expect(new URL(page.url()).searchParams.get("next")).toBe(path);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Sign in to Academic Wordbank" })).toBeVisible();
  });

  test(`FULL-NAV staff direct load and reload: ${path}`, async ({ page, request }) => {
    const errors = errorsOn(page);
    await staff(page, request);
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.locator("main#main")).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("FULL-LINK landing internal links and fragment targets resolve", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("h1")).toBeVisible();
  const links = await page.locator("a[href]").evaluateAll((anchors) => anchors.map((a) => a.getAttribute("href")!));
  expect(links.length).toBeGreaterThan(10);
  for (const href of [...new Set(links)]) {
    expect(href).not.toMatch(/^javascript:/i);
    if (href.startsWith("#")) {
      expect(await page.locator(`[id="${href.slice(1)}"]`).count(), `Missing fragment ${href}`).toBe(1);
    } else if (href.startsWith("/")) {
      const response = await page.request.get(href);
      expect(response.status(), href).toBe(200);
    } else {
      expect(new URL(href).protocol).toBe("https:");
    }
  }
});

test("FULL-LINK every sidebar link navigates to its screen", async ({ page, request }) => {
  await staff(page, request);
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Workspace", exact: true })).toBeVisible();
  const links = await page.locator('[data-sidebar="sidebar"] a[href]').evaluateAll((anchors) => anchors.map((a) => ({ href: a.getAttribute("href")!, text: a.textContent!.trim() })));
  expect(links.length).toBeGreaterThanOrEqual(10);
  for (const href of [...new Set(links.map((link) => link.href))]) {
    await page.locator(`[data-sidebar="sidebar"] a[href="${href}"]`).first().click();
    await expect.poll(() => new URL(page.url()).pathname).toBe(href);
    const screen = screens.find(([path]) => path === href);
    await expect(page.getByRole("heading", { name: screen?.[1] ?? "Writer", exact: true })).toBeVisible();
  }
});

test("FULL-LINK history back forward preserves a valid route", async ({ page, request }) => {
  await staff(page, request);
  await page.goto("/app");
  await page.getByRole("link", { name: "Phrasebank", exact: true }).first().click();
  await expect(page).toHaveURL(/\/phrasebank$/);
  await page.getByRole("link", { name: "Writer", exact: true }).first().click();
  await expect(page).toHaveURL(/\/writer$/);
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Phrasebank", exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("heading", { name: "Writer", exact: true })).toBeVisible();
});

test("FULL-LINK journal detail links keep the selected identity", async ({ page, request }) => {
  await staff(page, request);
  await page.goto("/journals");
  await page.getByRole("link", { name: /Journal of Applied Computing Research/ }).first().click();
  await expect(page).toHaveURL(/\/journals\/J-001$/);
  await expect(page.locator("main")).toContainText("Journal of Applied Computing Research");
});

for (const next of ["https://example.test/", "//example.test/", "/\\example.test/", "/\t/example.test/", "javascript:alert(1)", "x".repeat(2049)]) {
  test(`FULL-AUTH rejects unsafe next: ${JSON.stringify(next.slice(0, 40))}`, async ({ page, request }) => {
    await staff(page, request);
    await page.goto(`/signin?next=${encodeURIComponent(next)}`);
    await expect.poll(() => new URL(page.url()).pathname).toBe("/app");
    expect(new URL(page.url()).origin).toBe(new URL(test.info().project.use.baseURL!).origin);
  });
}

test("FULL-AUTH preserves safe next with query", async ({ page, request }) => {
  await staff(page, request);
  await page.goto("/signin?next=%2Flibrary%3Fp%3Dmissing");
  await expect(page).toHaveURL(/\/library\?p=missing$/);
  await expect(page.getByRole("heading", { name: "Pattern library" })).toBeVisible();
});

test("FULL-AUTH invalid saved session is removed and sign-in recovers", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("aprkb-staff-session", "invalid-full-test-key"));
  await page.goto("/inbox");
  await expect(page.getByRole("heading", { name: "Sign in to Academic Wordbank" })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem("aprkb-staff-session"))).toBeNull();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeDisabled();
  await page.getByLabel("Curator or admin API key").fill("   ");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeDisabled();
  await page.getByLabel("Curator or admin API key").fill("invalid-full-test-key");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Invalid or revoked API key");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeEnabled();
});

test("FULL-AUTH curator cannot load admin data", async ({ page, request }) => {
  await staff(page, request);
  const adminRequests: string[] = [];
  page.on("request", (r) => { if (new URL(r.url()).pathname.startsWith("/v1/admin/")) adminRequests.push(r.url()); });
  await page.goto("/admin");
  await expect(page.getByText("Admin role required", { exact: true })).toBeVisible();
  expect(adminRequests).toEqual([]);
  await expect(page.getByRole("link", { name: "Admin", exact: true })).toHaveCount(0);
});

for (const [width, height] of [[320, 700], [375, 812], [768, 1024], [1440, 900]]) {
  for (const path of ["/", "/signin", "/writer"]) {
    test(`FULL-BOUNDARY viewport ${width}x${height}: ${path}`, async ({ page }) => {
      const errors = errorsOn(page);
      await page.setViewportSize({ width, height });
      await page.goto(path);
      await expect(page.locator("h1").first()).toBeVisible();
      if (path === "/writer") await expect(page.getByRole("button", { name: "Find patterns", exact: true })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      expect(errors).toEqual([]);
      await page.screenshot({ path: test.info().outputPath(`viewport-${width}.png`), fullPage: true });
    });
  }
}

test("FULL-KEYBOARD guest command menu contains only Writer and escapes", async ({ page }) => {
  await page.goto("/writer");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("option", { name: "Writer", exact: true })).toBeVisible();
  await expect(page.getByRole("option", { name: "Inbox", exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("FULL-KEYBOARD staff command navigation and skip target", async ({ page, request }) => {
  await staff(page, request);
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Workspace", exact: true })).toBeVisible();
  await page.keyboard.press("Control+k");
  await page.getByPlaceholder("Go to screen…").fill("Inbox");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/inbox$/);
  await expect(page.getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
  await expect(page.locator("#main")).toHaveCount(1);
});

test("FULL-BOUNDARY unknown top-level URL has a useful not-found state", async ({ page }) => {
  const errors = errorsOn(page);
  await page.goto("/full-test-route-does-not-exist");
  await expect(page.locator("body")).toContainText(/not found/i);
  expect(errors).toEqual([]);
});

for (const [path, heading] of screens) {
  test(`FULL-BOUNDARY staff mobile 375px: ${path}`, async ({ page, request }) => {
    const errors = errorsOn(page);
    await staff(page, request);
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    await page.getByRole("button", { name: "Open navigation", exact: true }).click();
    await expect(page.getByRole("link", { name: "Writer", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Open navigation", exact: true })).toBeVisible();
    expect(errors).toEqual([]);
    await page.screenshot({ path: test.info().outputPath("staff-mobile.png"), fullPage: true });
  });
}

for (const [path, message] of [
  ["/phrasebank/pattern/not-a-uuid", "Pattern detail is unavailable"],
  ["/vocabulary/not-a-uuid", "Could not load this lemma"],
  ["/journals/missing-full-test", "Journal not found"],
]) {
  test(`FULL-EDGE invalid detail link is recoverable: ${path}`, async ({ page, request }) => {
    const errors = errorsOn(page);
    await staff(page, request);
    await page.goto(path);
    await expect(page.locator("main")).toContainText(message, { timeout: 15_000 });
    await page.getByRole("link", { name: "Writer", exact: true }).first().click();
    await expect(page.getByRole("heading", { name: "Writer", exact: true })).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test("FULL-AUTH sign-out removes saved key and protected access", async ({ page, request }) => {
  await staff(page, request);
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Workspace", exact: true })).toBeVisible();
  await page.locator('[data-sidebar="footer"] button').first().click();
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  expect(await page.evaluate(() => sessionStorage.getItem("aprkb-staff-session"))).toBeNull();
  // Client-side link navigation must remain guarded after the session is cleared.
  await page.getByRole("link", { name: "Open the library", exact: true }).click();
  await expect(page).toHaveURL(/\/signin\?next=%2Flibrary/);
});
