import { expect, test, type Page, type APIRequestContext } from "@playwright/test";

test.skip(process.env.ONLINE_RANKING_LIVE !== "1", "Requires isolated live API");

async function staff(page: Page, request: APIRequestContext) {
  const response = await request.post("/v1/auth/demo-session");
  expect(response.ok()).toBeTruthy();
  const { api_key: key } = await response.json();
  // Preserve real storage mutations across reload; do not reseed the setting.
  await page.addInitScript((key) => sessionStorage.setItem("aprkb-staff-session", key), key);
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Workspace", exact: true })).toBeVisible();
}

for (const width of [767, 768, 769]) {
  test(`EDGE-B01 mobile breakpoint ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await staff(page, request);
    const trigger = page.getByRole("button", { name: "Open navigation", exact: true });
    if (width < 768) {
      await expect(trigger).toBeVisible();
      await trigger.click();
      await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toHaveCount(0);
    } else {
      await expect(trigger).toBeHidden();
      await expect(page.getByRole("link", { name: "Inbox", exact: true })).toBeVisible();
    }
  });
}

for (const width of [1279, 1280, 1281]) {
  test(`EDGE-B02 phrasebank layout breakpoint ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await staff(page, request);
    await page.getByRole("link", { name: "Phrasebank", exact: true }).first().click();
    await expect(page.getByRole("heading", { name: "Phrasebank", exact: true })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  });
}

for (const height of [320, 480]) {
  test(`EDGE-B03 short viewport account menu 375x${height}`, async ({ page, request }) => {
    await page.setViewportSize({ width: 375, height });
    await staff(page, request);
    await page.getByRole("button", { name: "Open navigation", exact: true }).click();
    await page.locator('[data-sidebar="footer"] button').first().click();
    const signout = page.getByRole("menuitem", { name: "Sign out", exact: true });
    await expect(signout).toBeVisible();
    await expect.poll(async () => {
      const box = await signout.boundingBox();
      return Boolean(box && box.y >= 0 && box.y + box.height <= height);
    }).toBe(true);
    await signout.click();
    await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  });
}

test("EDGE-A01 mobile focus stays trapped for Tab and Shift+Tab", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await staff(page, request);
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toBeVisible();
  for (const key of [...Array<string>(18).fill("Tab"), ...Array<string>(18).fill("Shift+Tab")]) {
    await page.keyboard.press(key);
    expect(await page.evaluate(() => document.activeElement?.closest('[role="dialog"]')?.getAttribute("aria-label") ?? document.activeElement?.closest('[role="dialog"]')?.querySelector("h2")?.textContent)).toBe("Sidebar");
  }
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toHaveCount(0);
});

test("EDGE-A02 outside pointer dismisses mobile navigation", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await staff(page, request);
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toBeVisible();
  await page.mouse.click(365, 120);
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toHaveCount(0);
});

test("EDGE-A03 account menu works with keyboard and Escape does not sign out", async ({ page, request }) => {
  await staff(page, request);
  const before = await page.evaluate(() => sessionStorage.getItem("aprkb-staff-session"));
  await page.locator('[data-sidebar="footer"] button').first().focus();
  await page.keyboard.press("ArrowDown");
  await expect(page.getByRole("menu")).toBeVisible();
  await page.keyboard.press("End");
  await expect(page.getByRole("menuitem", { name: "Sign out", exact: true })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  expect(await page.evaluate(() => sessionStorage.getItem("aprkb-staff-session"))).toBe(before);
});

test("EDGE-S01 sidebar collapse persists across real reload", async ({ page, request }) => {
  await staff(page, request);
  await page.keyboard.press("Control+b");
  await expect(page.locator('[data-slot="sidebar"][data-state="collapsed"]')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("aprkb.sidebar.collapsed"))).toBe("1");
  await page.reload();
  await expect(page.locator('[data-slot="sidebar"][data-state="collapsed"]')).toBeVisible();
  await page.keyboard.press("Control+b");
  await expect(page.locator('[data-slot="sidebar"][data-state="expanded"]')).toBeVisible();
});

test("EDGE-S02 theme action persists in session and reverses", async ({ page, request }) => {
  await staff(page, request);
  for (const [action, theme] of [["Dark theme", "dark"], ["Light theme", "light"]]) {
    await page.locator('[data-sidebar="footer"] button').first().click();
    await page.getByRole("menuitem", { name: action, exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Workspace", exact: true })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
  }
});

test("EDGE-S03 changing orientation restores usable mobile navigation", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await staff(page, request);
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 1024, height: 600 });
  await expect(page.getByRole("link", { name: "Inbox", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toBeVisible();
  await expect(page.locator('[data-slot="tooltip-content"]')).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toHaveCount(0);
});

test("EDGE-R01 transport failure can recover with a fresh recommendation", async ({ page }) => {
  await page.goto("/writer");
  await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toBeVisible();
  await page.route("**/v1/recommendations", (route) => route.abort("internetdisconnected"));
  await page.getByLabel("Search keywords").fill("suggests");
  await page.getByRole("button", { name: "Find patterns", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.unroute("**/v1/recommendations");
  await page.getByRole("button", { name: "Find patterns", exact: true }).click();
  await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toContainText("We suggest");
});
