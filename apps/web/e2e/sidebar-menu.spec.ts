import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { authenticateCurator } from "./support/auth";

test.skip(process.env.ONLINE_RANKING_LIVE !== "1", "Requires isolated live API");

async function login(page: Page, request: APIRequestContext, collapsed = false) {
  await authenticateCurator(page, request);
  await page.addInitScript(({ collapsed }) => {
    localStorage.setItem("aprkb.sidebar.collapsed", collapsed ? "1" : "0");
  }, { collapsed });
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Workspace", exact: true })).toBeVisible();
}

async function expectMenuInViewport(page: Page) {
  const item = page.getByRole("menuitem", { name: "Sign out", exact: true });
  await expect(item).toBeVisible();
  await expect.poll(async () => {
    const box = await item.boundingBox();
    const viewport = page.viewportSize()!;
    return Boolean(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width && box.y + box.height <= viewport.height);
  }).toBe(true);
}

test("MENU mobile default focus needs only one Escape on every opening", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await login(page, request);
  for (let attempt = 0; attempt < 3; attempt++) {
    await page.getByRole("button", { name: "Open navigation", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toBeVisible();
    await expect(page.locator('[data-slot="tooltip-content"]')).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toHaveCount(0);
  }
});

test("MENU mobile nested menu dismisses before the sidebar", async ({ page, request }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await login(page, request);
  await page.getByRole("button", { name: "Open navigation", exact: true }).click();
  await page.locator('[data-sidebar="footer"] button').first().click();
  await expectMenuInViewport(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Sidebar", exact: true })).toHaveCount(0);
});

test("MENU icon sidebar keeps tooltips and anchors account menu", async ({ page, request }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await login(page, request, true);
  await page.getByRole("link", { name: "Phrasebank", exact: true }).hover();
  await expect(page.getByRole("tooltip")).toContainText("Phrasebank");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await page.locator('[data-sidebar="footer"] button').first().click();
  await expectMenuInViewport(page);
  await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
  await expect.poll(() => new URL(page.url()).pathname).toBe("/");
  expect(await page.evaluate(() => sessionStorage.getItem("aprkb-web-session"))).toBeNull();
});

for (const width of [320, 375, 768, 1280, 1440]) {
  test(`MENU account actions are inside viewport and sign out at ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await login(page, request);
    if (width < 768) await page.getByRole("button", { name: "Open navigation", exact: true }).click();
    await page.locator('[data-sidebar="footer"] button').first().click();
    await expectMenuInViewport(page);
    await page.screenshot({ path: test.info().outputPath(`account-menu-${width}.png`) });
    await page.getByRole("menuitem", { name: "Sign out", exact: true }).click();
    await expect.poll(() => new URL(page.url()).pathname).toBe("/");
    expect(await page.evaluate(() => sessionStorage.getItem("aprkb-web-session"))).toBeNull();
  });
}
