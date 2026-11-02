import { mkdirSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const baseURL = process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173";
const screenshots = "C:/Users/khact/AppData/Local/Temp/claude/phrasebank-screens";
const notice = {
  name: "Example University Phrase Library",
  url: "https://example.test/",
  license_status: "unknown",
  rights_status: "unverified",
  notice: "Example source notice for tests.",
};
const categories = [
  { slug: "section-one", title: "Section One", kind: "section", position: 0, entry_count: 4 },
  { slug: "function-one", title: "Function One", kind: "function", position: 1, entry_count: 1 },
];
const detail = {
  source: notice,
  category: categories[0],
  headings: [
    { heading: "Section One", heading_position: 0, entries: [
      { id: "intro", heading: "Section One", heading_position: 0, block_index: 0, kind: "note", text: "Intro note", cells: null, position: 0 },
    ] },
    { heading: "Ordered heading", heading_position: 1, entries: [
      { id: "row-a", heading: "Ordered heading", heading_position: 1, block_index: 1, kind: "phrase", text: null, cells: [["Alpha"], ["beta", "beta"]], position: 1 },
      { id: "row-b", heading: "Ordered heading", heading_position: 1, block_index: 1, kind: "phrase", text: null, cells: [["gamma"], ["delta"]], position: 2 },
      { id: "note-after", heading: "Ordered heading", heading_position: 1, block_index: 2, kind: "note", text: "Paragraph after the first table.", cells: null, position: 3 },
      { id: "row-c", heading: "Ordered heading", heading_position: 1, block_index: 3, kind: "phrase", text: null, cells: [["epsilon"], ["zeta"], ["eta"]], position: 4 },
    ] },
    { heading: "Final heading", heading_position: 2, entries: [
      { id: "final", heading: "Final heading", heading_position: 2, block_index: 0, kind: "note", text: "Final note", cells: null, position: 5 },
    ] },
  ],
};
const search = {
  source: notice,
  query: "alpha",
  results: [
    { category_slug: "section-one", category_title: "Section One", heading: "Ordered heading", entry: detail.headings[1]!.entries[0]! },
    { category_slug: "section-one", category_title: "Section One", heading: "Final heading", entry: detail.headings[2]!.entries[0]! },
    { category_slug: "function-one", category_title: "Function One", heading: "Function One", entry: { ...detail.headings[0]!.entries[0]!, id: "function-result", text: "Alpha result" } },
  ],
};
const patterns = [{
  id: "pattern-1", status: "approved", intent_code: "INTRO_GAP_INDICATE", canonical_frame: "Invented {topic} frame",
  version_no: 1, current_version_id: "version-1", slots: {}, epistemic_strength: "moderate", claim_type: "descriptive",
  allowed_sections: ["INTRO"], allowed_genres: ["RESEARCH_ARTICLE"],
}];

test.use({ baseURL, browserName: "chromium" });

async function authenticate(page: Page) {
  await page.addInitScript(() => sessionStorage.setItem("aprkb-staff-session", "test-staff-key"));
  await page.route("**/v1/auth/me", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ id: "test-id", name: "Test curator", role: "curator" }),
  }));
}

async function mockLibrary(page: Page) {
  await page.route("**/v1/reference-library/categories/section-one", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(detail),
  }));
  await page.route("**/v1/reference-library/categories", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ source: notice, categories }),
  }));
  await page.route("**/v1/reference-library/search**", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(search),
  }));
  await page.route("**/v1/patterns**", (route) => {
    const isDetail = new URL(route.request().url()).pathname.endsWith("/pattern-1");
    return route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify(isDetail ? patterns[0] : patterns),
    });
  });
}

test("home shows section/function counts, source filtering and a screenshot without key warnings", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  await expect(page.getByRole("heading", { name: "Sections" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "General functions" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Section One/ })).toBeVisible();
  await expect(page.getByText("4 entries")).toBeVisible();
  await expect(page.getByRole("link", { name: /Function One/ })).toBeVisible();
  await expect(page.getByText("1 entries")).toBeVisible();
  await page.screenshot({ path: `${screenshots}/phrasebank-home.png`, fullPage: true });

  const filter = page.getByRole("combobox", { name: "Source filter" });
  await filter.selectOption("manchester-reference");
  await expect(page.getByRole("heading", { name: "AP-RKB patterns" })).toHaveCount(0);
  await filter.selectOption("aprkb-patterns");
  await expect(page.getByRole("heading", { name: "Sections" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Use in Writer" })).toBeVisible();
  expect(consoleErrors.filter((message) => /unique "key" prop/i.test(message))).toEqual([]);
});

test("category keeps source order, separate table shapes, index navigation, copy and screenshot", async ({ page, context }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank/section-one");
  const heading = page.locator("#heading-section-one-1");
  await expect(heading.locator(".phrasebank-table")).toHaveCount(2);
  await expect(heading.locator(".phrasebank-table").nth(0).locator("tr")).toHaveCount(2);
  await expect(heading.locator(".phrasebank-table").nth(0).locator("tr").first().locator("td")).toHaveCount(3);
  await expect(heading.locator(".phrasebank-table").nth(1).locator("tr").first().locator("td")).toHaveCount(4);
  const order = await heading.locator(":scope > .phrasebank-entry-list").evaluate((list) =>
    [...list.children].map((element) => element.matches("p") ? "paragraph" : "table"));
  expect(order).toEqual(["table", "paragraph", "table"]);
  await page.screenshot({ path: `${screenshots}/phrasebank-category.png`, fullPage: true });

  await page.getByRole("link", { name: "Final heading" }).click();
  await expect(page).toHaveURL(/#heading-section-one-2$/);
  await expect.poll(() => page.locator("#heading-section-one-2").evaluate((element) => {
    const { top } = element.getBoundingClientRect();
    return window.scrollY > 0 && top >= 0 && top < window.innerHeight;
  })).toBe(true);
  const jump = await page.locator("#heading-section-one-2").evaluate((element) => ({ top: element.getBoundingClientRect().top, viewport: window.innerHeight, scrollY: window.scrollY }));
  expect(jump.scrollY).toBeGreaterThan(0);
  expect(jump.top).toBeGreaterThanOrEqual(0);
  expect(jump.top).toBeLessThan(jump.viewport);
  await page.getByRole("button", { name: "Copy phrase row" }).first().click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("Alpha beta / beta");
  expect(consoleErrors.filter((message) => /unique "key" prop/i.test(message))).toEqual([]);
});

test("search groups results by category then heading and opens the category heading", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  const searchBox = page.getByRole("searchbox", { name: "Search phrasebanks" });
  await expect(searchBox).toBeVisible();
  await searchBox.fill("alpha");
  await expect(page.getByRole("link", { name: "Open heading" }).first()).toBeVisible();
  const renderedGroups = await page.locator("h3").evaluateAll((headings) => headings
    .filter((heading) => ["Section One", "Function One"].includes(heading.textContent?.trim() ?? ""))
    .map((heading) => ({
      category: heading.textContent?.trim(),
      headings: [...(heading.closest("section")?.querySelectorAll("h4") ?? [])].map((item) => item.textContent?.trim()),
    })));
  expect(renderedGroups).toEqual([
    { category: "Section One", headings: ["Ordered heading", "Final heading"] },
    { category: "Function One", headings: ["Function One"] },
  ]);
  await page.getByRole("link", { name: "Open heading" }).first().click();
  await expect(page).toHaveURL(/\/phrasebank\/section-one#heading-section-one-1$/);
  await expect.poll(() => page.locator("#heading-section-one-1").evaluate((element) => {
    const { top } = element.getBoundingClientRect();
    return window.scrollY > 0 && top >= 0 && top < window.innerHeight;
  })).toBe(true);
});

test("disabled Manchester collection displays its disabled state", async ({ page }) => {
  await authenticate(page);
  await page.route("**/v1/reference-library/**", (route) => route.fulfill({
    status: 404, contentType: "application/json",
    body: JSON.stringify({ error: { code: "NOT_FOUND", message: "Reference library is disabled", details: null }, request_id: "test" }),
  }));
  await page.route("**/v1/patterns**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.goto("/phrasebank");
  await expect(page.getByText(/Manchester reference is disabled/).first()).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Source filter" })).toHaveValue("all");
});

test("AP-RKB category shows the Writer cross link", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank/aprkb-patterns");
  await expect(page.getByText("Invented {topic} frame")).toBeVisible();
  await expect(page.getByRole("link", { name: "Use in Writer" })).toHaveAttribute("href", "/writer");
});

test.beforeAll(() => mkdirSync(screenshots, { recursive: true }));
