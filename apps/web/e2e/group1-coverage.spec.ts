import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

test.skip(process.env.ONLINE_RANKING_LIVE !== "1", "Requires the isolated live Group 1 API");
test.use({
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

async function select(page: Page, name: string, label: string) {
  await page.getByRole("combobox", { name, exact: true }).click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

async function rhetoric(request: APIRequestContext) {
  const response = await request.get("/v1/taxonomy");
  expect(response.ok()).toBeTruthy();
  const taxonomy = await response.json();
  const section = taxonomy.sections.find((s: { code: string }) => s.code === "INTRO");
  const move = section.moves.find((m: { steps: { intents: { code: string }[] }[] }) =>
    m.steps.some((s) => s.intents.some((i) => i.code === "INTRO_GAP_INDICATE")));
  const intent = move.steps.flatMap((s: { intents: { code: string; name: string }[] }) => s.intents)
    .find((i: { code: string }) => i.code === "INTRO_GAP_INDICATE");
  return { section, move, intent };
}

async function openWriter(page: Page) {
  await page.goto("/writer");
  await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toBeVisible();
}

test("APRKB_G1_TC_050 genre changes clear section, move and intent", async ({ page, request }) => {
  const { section, move, intent } = await rhetoric(request);
  await openWriter(page);
  await select(page, "Manuscript section", section.name);
  await select(page, "Rhetorical move", move.name);
  await select(page, "Rhetorical intent", intent.name);
  await select(page, "Article genre", "Research article");
  await expect(page.getByRole("combobox", { name: "Manuscript section", exact: true })).toContainText("Any section");
  await expect(page.getByRole("combobox", { name: "Rhetorical move", exact: true })).toContainText("Any move");
  await expect(page.getByRole("combobox", { name: "Rhetorical intent", exact: true })).toContainText("Any intent");
  await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toHaveCount(0);
});

test("APRKB_G1_TC_051 move changes clear intent and preserve section", async ({ page, request }) => {
  const { section, move, intent } = await rhetoric(request);
  await openWriter(page);
  await select(page, "Manuscript section", section.name);
  await select(page, "Rhetorical move", move.name);
  await select(page, "Rhetorical intent", intent.name);
  await select(page, "Rhetorical move", "Any move");
  await expect(page.getByRole("combobox", { name: "Rhetorical intent", exact: true })).toContainText("Any intent");
  await expect(page.getByRole("combobox", { name: "Manuscript section", exact: true })).toContainText(section.name);
});

test("APRKB_G1_TC_052 query length is capped at 500 characters", async ({ page }) => {
  await openWriter(page);
  const query = page.getByLabel("Search keywords");
  await query.fill("x".repeat(501));
  await expect(query).toHaveValue("x".repeat(500));
});

test("APRKB_G1_TC_053 backend 503 is visible and a later search recovers", async ({ page }) => {
  await openWriter(page);
  await page.getByLabel("Search keywords").fill("suggests");
  await page.route("**/v1/recommendations", (route) => route.fulfill({
    status: 503, contentType: "application/json",
    body: JSON.stringify({ error: { code: "HTTP_ERROR", message: "Fixture unavailable" } }),
  }));
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByRole("alert")).toContainText("Policy or reference data is unavailable");
  await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toHaveCount(0);
  await page.unroute("**/v1/recommendations");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText("We suggest {topic}.", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "HTTP 503" })).toHaveCount(0);
});

test("APRKB_G1_TC_054 a delayed response cannot restore results after context changes", async ({ page }) => {
  await openWriter(page);
  let release!: () => void;
  let intercepted!: () => void;
  const responseGate = new Promise<void>((resolve) => { release = resolve; });
  const captured = new Promise<void>((resolve) => { intercepted = resolve; });
  await page.route("**/v1/recommendations", async (route) => {
    const response = await route.fetch();
    intercepted();
    await responseGate;
    await route.fulfill({ response });
  });
  try {
    await page.getByLabel("Search keywords").fill("suggests");
    await page.getByRole("button", { name: "Find patterns" }).click();
    await captured;
    await page.getByLabel("Search keywords").fill("zzzznomatch987");
    const settled = page.waitForResponse((response) => response.url().endsWith("/v1/recommendations"));
    release();
    await settled;
    await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toHaveCount(0);
    await expect(page.getByText("We suggest {topic}.", { exact: true })).toHaveCount(0);
  } finally {
    release();
    await page.unroute("**/v1/recommendations");
  }
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText("No patterns meet these criteria.", { exact: false })).toBeVisible();
});

test("APRKB_G1_TC_055 move can be chosen and the form submitted by keyboard", async ({ page, request }) => {
  const { section, move } = await rhetoric(request);
  await openWriter(page);
  await select(page, "Manuscript section", section.name);
  const combo = page.getByRole("combobox", { name: "Rhetorical move", exact: true });
  await combo.focus();
  await combo.press("Enter");
  await page.getByRole("option", { name: move.name, exact: true }).press("Enter");
  await expect(combo).toContainText(move.name);
  await page.getByLabel("Search keywords").fill("suggests");
  const pending = page.waitForResponse((response) => response.url().endsWith("/v1/recommendations"));
  await page.getByLabel("Search keywords").press("Enter");
  const response = await pending;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toMatchObject({ move: move.code, intent: null });
  await expect(page.getByText("We suggest {topic}.", { exact: true })).toBeVisible();
});

test("APRKB_G1_TC_056 empty results cannot expose a stale composer or copy action", async ({ page }) => {
  await openWriter(page);
  await page.getByLabel("Search keywords").fill("zzzznomatch987");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText("No patterns meet these criteria.", { exact: false })).toBeVisible();
  await expect(page.getByRole("radio")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Build sentence" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Copy draft" })).toHaveCount(0);
});

test("APRKB_G1_TC_057 query markup is displayed as text and does not execute", async ({ page }) => {
  await openWriter(page);
  const dialogs: string[] = [];
  page.on("dialog", async (dialog) => { dialogs.push(dialog.message()); await dialog.dismiss(); });
  const query = "<img src=x onerror=alert(1)>";
  await page.getByLabel("Search keywords").fill(query);
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText(`"${query}"`, { exact: true })).toBeVisible();
  expect(dialogs).toEqual([]);
  await expect(page.locator("img[onerror]")).toHaveCount(0);
});

test("APRKB_G1_TC_058 supporting context length is capped at 2000", async ({ page }) => {
  await openWriter(page);
  const supporting = page.getByLabel("Supporting context");
  await supporting.fill("v".repeat(2001));
  await expect(supporting).toHaveValue("v".repeat(2000));
  await expect(page.getByLabel("Search keywords")).toHaveValue("");
});

test("APRKB_G1_TC_059 changing supporting evidence invalidates validation and preserves draft", async ({ page }) => {
  await openWriter(page);
  await page.getByLabel("Search keywords").fill("suggests");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await page.getByRole("radio", { name: "Select We suggest {topic}.", exact: true }).click();
  await page.getByRole("textbox", { name: /^\{topic\}/ }).fill("a careful interpretation");
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByLabel("Draft sentence")).toHaveValue("We suggest a careful interpretation.");
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText(/^Claim check/)).toBeVisible();
  await page.getByLabel("Supporting context").fill("A changed evidence summary.");
  await expect(page.getByText(/^Claim check/)).toHaveCount(0);
  await expect(page.getByLabel("Draft sentence")).toHaveValue("We suggest a careful interpretation.");
  // Resetting validation removes the copy action entirely, rather than disabling it.
  await expect(page.getByRole("button", { name: "Copy draft" })).toHaveCount(0);
});

test("APRKB_G1_TC_060 double submit does not issue a second pending search", async ({ page }) => {
  await openWriter(page);
  let release!: () => void;
  let intercepted!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const captured = new Promise<void>((resolve) => { intercepted = resolve; });
  let calls = 0;
  await page.route("**/v1/recommendations", async (route) => {
    calls += 1;
    const response = await route.fetch();
    intercepted();
    await gate;
    await route.fulfill({ response });
  });
  try {
    await page.getByLabel("Search keywords").fill("suggests");
    await page.getByRole("button", { name: "Find patterns" }).dblclick();
    await captured;
    await expect(page.getByRole("button", { name: "Searching…" })).toBeDisabled();
    expect(calls).toBe(1);
    release();
    await expect(page.getByText("We suggest {topic}.", { exact: true })).toBeVisible();
  } finally {
    release();
    await page.unroute("**/v1/recommendations");
  }
});
