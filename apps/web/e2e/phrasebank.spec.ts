import { mkdirSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const baseURL = process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173";
const sourceCredit = "Source: University of Manchester Academic Phrasebank.";
const screenshots = process.env.E2E_SCREENSHOT_DIR ?? "test-results/phrasebank-screens";
const notice = {
  name: "Example University Phrase Library",
  url: "https://example.test/",
  license_status: "unknown",
  rights_status: "unverified",
  notice: "Example source notice for tests.",
};
const categories = [
  { slug: "section-one", title: "Section One", kind: "section", position: 0, entry_count: 4, unmapped_entry_count: 0, unmapped_section_entry_count: 0, unmapped_intent_entry_count: 1, source_url: "https://example.test/source/", resolved_url: "https://example.test/resolved/", captured_at: "2026-01-01", html_sha256: "a".repeat(64), source_category: "fixture", license_status: "unknown", rights_status: "unverified", status: "quarantined", note: "Fixture metadata", extraction_method: "fixture", section_code: "INTRO", general_function_code: null, intent_codes: ["INTRO_GAP_INDICATE"], review_status: "proposed" },
  { slug: "function-one", title: "Function One", kind: "function", position: 1, entry_count: 1, unmapped_entry_count: 1, unmapped_section_entry_count: 1, unmapped_intent_entry_count: 1, source_url: "https://example.test/function/", resolved_url: "https://example.test/function-resolved/", captured_at: "2026-01-01", html_sha256: "b".repeat(64), source_category: "fixture", license_status: "unknown", rights_status: "unverified", status: "quarantined", note: "Fixture metadata", extraction_method: null, section_code: null, general_function_code: null, intent_codes: [], review_status: null },
];
const detail = {
  source: notice,
  category: categories[0]!,
  headings: [
    { heading: "Section One", heading_position: 0, intent_code: null, review_status: null, entries: [
      { id: "intro", heading: "Section One", heading_position: 0, block_index: 0, block_id: "intro-0", kind: "note", text: "Intro note", cells: null, position: 0 },
    ] },
    { heading: "Ordered heading", heading_position: 1, intent_code: "INTRO_GAP_INDICATE", review_status: "proposed", entries: [
      { id: "row-a", heading: "Ordered heading", heading_position: 1, block_index: 1, block_id: "table-a", kind: "phrase", text: null, cells: [["Alpha"], ["beta", "beta"]], position: 1 },
      { id: "row-b", heading: "Ordered heading", heading_position: 1, block_index: 1, block_id: "table-a", kind: "phrase", text: null, cells: [["gamma"], ["delta"]], position: 2 },
      { id: "note-after", heading: "Ordered heading", heading_position: 1, block_index: 2, block_id: "note-2", kind: "note", text: "Paragraph after the first table.", cells: null, position: 3 },
      { id: "row-c", heading: "Ordered heading", heading_position: 1, block_index: 3, block_id: "table-b", kind: "phrase", text: null, cells: [["epsilon"], ["zeta"], ["eta"]], position: 4 },
    ] },
    { heading: "Final heading", heading_position: 2, intent_code: null, review_status: null, entries: [
      { id: "final", heading: "Final heading", heading_position: 2, block_index: 0, block_id: "final-0", kind: "note", text: "Final note", cells: null, position: 5 },
    ] },
  ],
};
const search = {
  source: notice,
  query: "alpha",
  results: [
    { category_slug: "section-one", category_title: "Section One", heading: "Ordered heading", entry: detail.headings[1]!.entries[0]!, section_code: "INTRO", intent_code: "INTRO_GAP_INDICATE", review_status: "proposed" },
    { category_slug: "section-one", category_title: "Section One", heading: "Final heading", entry: detail.headings[2]!.entries[0]!, section_code: "INTRO", intent_code: null, review_status: "proposed" },
    { category_slug: "function-one", category_title: "Function One", heading: "Function One", entry: { ...detail.headings[1]!.entries[0]!, id: "function-result", heading: "Function One", cells: [["Alpha"], ["result"]] }, section_code: null, intent_code: null, review_status: null },
  ],
};
const taxonomy = {
  release_id: "release-fixture", version: "0.1.0",
  sections: [
    { id: "section-intro", code: "INTRO", name: "Introduction", order: 1, moves: [{ id: "move-fixture", code: "INTRO_MOVE", name: "Invented move", steps: [{ id: "step-fixture", code: "INTRO_STEP", name: "Invented step", intents: [{ id: "intent-fixture", code: "INTRO_GAP_INDICATE", name: "Invented intent", description: null }] }] }] },
    { id: "section-results", code: "RESULTS", name: "Results", order: 2, moves: [] },
  ],
  article_genres: [],
};
const patterns = [{
  id: "pattern-1", status: "approved", intent_code: "INTRO_GAP_INDICATE", canonical_frame: "Alpha invented {topic} frame",
  intent_name: "Invented intent", version_no: 1, current_version_id: "version-1",
  slots: { topic: { type: "topic", label: "Topic", instruction: "Name an invented topic", example: "invented method", required: true, min_length: 1 } },
  epistemic_strength: null, epistemic_strength_labelled: false, claim_type: null, claim_type_labelled: false,
  variants: [{ text: "Invented alternative {topic}", register: "formal" }],
  evidence_min: "single_study", forbidden_contexts: ["DISCUSSION"],
  allowed_sections: ["INTRO"], allowed_genres: ["RESEARCH_ARTICLE"],
  source_type: "mined", license_code: "CC-BY", license_name: "Creative Commons Attribution",
  license_allows_display: true, license_flag: false, article_id: "article-1", source_reference: null,
  source_sentence_count: 2, discipline_affinities: [],
}];

test.use({
  baseURL,
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

async function authenticate(page: Page) {
  await page.addInitScript(() => sessionStorage.setItem("aprkb-web-session", "test-staff-key"));
  await page.route("**/v1/auth/session/me", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ id: "test-id", name: "Test curator", role: "curator" }),
  }));
}

async function mockLibrary(page: Page) {
  await page.route("**/v1/taxonomy", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(taxonomy) }));
  await page.route("**/v1/reference-library/categories/section-one", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(detail),
  }));
  await page.route("**/v1/reference-library/categories", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ source: notice, categories }),
  }));
  await page.route("**/v1/reference-library/search**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    const filtered = search.results.filter((item) =>
      (!params.get("section") || item.section_code === params.get("section"))
      && (!params.get("intent") || item.intent_code === params.get("intent"))
      && (params.get("phrase_only") !== "true" || item.entry.kind === "phrase"));
    return route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ...search, results: filtered }),
    });
  });
  await page.route("**/v1/patterns**", (route) => {
    const url = new URL(route.request().url());
    const isDetail = url.pathname.endsWith("/pattern-1");
    const params = url.searchParams;
    const filtered = patterns.filter((item) =>
      (!params.get("section") || item.allowed_sections.includes(params.get("section")!))
      && (!params.get("intent") || item.intent_code === params.get("intent"))
      && (!params.get("q") || `${item.canonical_frame} ${item.intent_code} ${item.allowed_sections.join(" ")}`.toLowerCase().includes(params.get("q")!.toLowerCase())));
    return route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify(isDetail ? patterns[0] : filtered),
    });
  });
}

// The redesigned filters are Radix comboboxes, not native <select> elements.
async function selectFilter(page: Page, name: string, option: string) {
  await page.getByRole("combobox", { name, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
  await expect(page.getByRole("combobox", { name, exact: true })).toContainText(option);
}

function cardTitle(page: Page, text: string) {
  return page.locator('[data-slot="card-title"]').filter({ hasText: new RegExp(`^${text}$`) });
}
function patternGroup(page: Page, title: string) {
  return page.locator("details").filter({ has: page.locator("summary").filter({ hasText: title }) });
}

test("home uses compact expandable groups and source filtering without key warnings", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  await expect(cardTitle(page, "Sections")).toBeVisible();
  await expect(cardTitle(page, "General functions")).toBeVisible();
  await expect(page.getByRole("link", { name: /Section One/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Phrasebank", exact: true })).toBeVisible();
  await expect(page.getByText("Reference library", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/Browse source-aware phrase collections/)).toHaveCount(0);
  await expect(page.getByText("4 reference items")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Function One/ })).toBeVisible();
  await expect(page.getByText("1 reference item")).toHaveCount(0);
  const cards = page.getByRole("link").filter({ has: page.locator('[data-slot="badge"]') });
  await expect(cards).toHaveCount(2);
  await expect(cards.locator('[data-slot="badge"]')).toHaveText(["4", "1"]);
  await expect(cards.first()).toContainText("Section One");
  await expect(cards.locator('[data-slot="badge"]')).toHaveCount(2);
  expect(await cards.first().evaluate((card) => card.querySelector('[data-slot="badge"]')!.getBoundingClientRect().right <= card.getBoundingClientRect().right)).toBe(true);
  await expect(page.getByText("Source: University of Manchester Academic Phrasebank.")).toHaveCount(1);
  await expect(page.getByText(sourceCredit, { exact: true })).toHaveCSS("font-weight", "400");
  await expect(page.getByText(sourceCredit, { exact: true })).toBeVisible();
  await expect(page.getByText(notice.notice, { exact: true })).toHaveCount(0);
  await expect(patternGroup(page, "INTRO · Invented intent")).toBeVisible();
  await expect(page.getByText("Alpha invented {topic} frame")).toBeHidden();
  await page.screenshot({ path: `${screenshots}/phrasebank-home-v2.png`, fullPage: true });
  await patternGroup(page, "INTRO · Invented intent").locator("summary").click();
  await expect(page.getByText("Alpha invented {topic} frame")).toBeVisible();
  // ADR-0011 supports desktop widths starting at 1024px.
  await page.setViewportSize({ width: 1024, height: 768 });
  for (const card of await cards.all()) {
    expect(await card.evaluate((element) => {
      const pill = element.querySelector('[data-slot="badge"]')!;
      return pill.getBoundingClientRect().right <= element.getBoundingClientRect().right;
    })).toBe(true);
  }
  await page.setViewportSize({ width: 1280, height: 720 });
  await expect(cardTitle(page, "General functions")).toBeVisible();
  await selectFilter(page, "Source filter", "Manchester reference");
  await expect(page.getByRole("link", { name: "AP-RKB patterns", exact: true })).toHaveCount(0);
  await selectFilter(page, "Source filter", "AP-RKB patterns");
  await expect(cardTitle(page, "Sections")).toHaveCount(0);
  await patternGroup(page, "INTRO · Invented intent").locator("summary").click();
  await expect(page.getByRole("link", { name: "Use in writer" })).toBeVisible();
  expect(consoleErrors.filter((message) => /unique "key" prop/i.test(message))).toEqual([]);
});

test("category keeps source order, separate table shapes, index navigation, copy and screenshot", async ({ page, context }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  // Keep a supported desktop width, but make the fixture taller than the viewport
  // so the anchor check proves navigation scrolls rather than merely changing the URL.
  await page.setViewportSize({ width: 1280, height: 480 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank/section-one");
  await expect(page.locator('[data-slot="badge"]')).toHaveCount(0);
  await expect(page.getByText(sourceCredit, { exact: true })).toHaveText("Source: University of Manchester Academic Phrasebank.");
  await expect(page.getByText("Intro note")).toHaveCount(0);
  await expect(page.getByText("Paragraph after the first table.")).toHaveCount(0);
  await expect(page.getByText("Final note")).toHaveCount(0);
  await expect.poll(() => page.getByRole("navigation", { name: "In-page headings" }).evaluate((element) => getComputedStyle(element).position)).not.toBe("sticky");
  const heading = page.locator("#heading-section-one-1");
  await expect(heading.getByRole("table")).toHaveCount(2);
  await expect(heading.getByRole("table").nth(0).locator("tr")).toHaveCount(2);
  await expect(heading.getByRole("table").nth(0).locator("tr").first().locator("td")).toHaveCount(3);
  await expect(heading.getByRole("table").nth(1).locator("tr").first().locator("td")).toHaveCount(4);
  await expect(heading.getByRole("table").nth(0).locator("td")).toHaveText([
    "Alpha", "betabeta", "Copy", "gamma", "delta", "Copy",
  ]);
  await expect(heading.getByRole("table").nth(1).locator("td")).toHaveText([
    "epsilon", "zeta", "eta", "Copy",
  ]);
  const order = await heading.locator(":scope > div").evaluate((list) =>
    [...list.children].map((element) => element.querySelector("table") ? "table" : "paragraph"));
  expect(order).toEqual(["table", "table"]);
  await expect(heading.locator('[data-slot="badge"]')).toHaveCount(0);
  await expect(heading.getByRole("table").locator('[data-slot="badge"]')).toHaveCount(0);
  const copyButtons = heading.getByRole("button", { name: "Copy phrase row" });
  await expect(copyButtons).toHaveCount(3);
  await expect(copyButtons.first()).toBeEnabled();
  await page.screenshot({ path: `${screenshots}/phrasebank-category-v2.png`, fullPage: true });

  await page.getByRole("link", { name: "Final heading" }).click();
  await expect(page).toHaveURL(/#heading-section-one-2$/);
  await expect.poll(() => page.locator("#heading-section-one-2").evaluate((element) => {
    const { top } = element.getBoundingClientRect();
    return window.scrollY > 0 && top >= 0 && top < window.innerHeight;
  })).toBe(true);
  const jump = await page.locator("#heading-section-one-2").evaluate((element) => ({ top: element.getBoundingClientRect().top, viewport: window.innerHeight, scrollY: window.scrollY }));
  expect(jump.scrollY).toBeGreaterThan(0);
  // The desktop shell has no fixed top header to offset.
  expect(jump.top).toBeGreaterThanOrEqual(0);
  expect(jump.top).toBeLessThan(jump.viewport);
  await page.getByRole("button", { name: "Copy phrase row" }).first().click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toBe("Alpha beta / beta");
  expect(consoleErrors.filter((message) => /unique "key" prop/i.test(message))).toEqual([]);
});

test("search groups results by category then heading and opens the category heading", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 480 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  const searchBox = page.getByRole("searchbox", { name: "Search phrasebanks" });
  await expect(searchBox).toBeVisible();
  await searchBox.fill("alpha");
  await expect(page.getByRole("link", { name: "Open heading" }).first()).toBeVisible();
  const searchPhrase = page.getByRole("table").first();
  await expect(searchPhrase).toHaveAccessibleName("Phrases under Ordered heading");
  await expect(searchPhrase.locator("td")).toHaveCount(2);
  await expect(searchPhrase.locator("td").nth(1).locator("div")).toHaveText(["beta", "beta"]);
  await expect(searchPhrase.locator("mark")).toHaveText("Alpha");
  await expect(page.getByText("Final note")).toHaveCount(0);
  await expect(page.getByText("Intro note")).toHaveCount(0);
  const renderedGroups = await page.locator("h4").evaluateAll((headings) => headings
    .filter((heading) => ["Section One", "Function One"].includes(heading.textContent?.trim() ?? ""))
    .map((heading) => ({
      category: heading.textContent?.trim(),
      headings: [...(heading.closest("section")?.querySelectorAll("h5") ?? [])].map((item) => item.textContent?.trim()),
    })));
  expect(renderedGroups).toEqual([
    { category: "Section One", headings: ["Ordered heading"] },
    { category: "Function One", headings: ["Function One"] },
  ]);
  await expect(page.getByRole("heading", { name: "Manchester reference" })).toBeVisible();
  await expect(page.getByText(sourceCredit, { exact: true })).toHaveText("Source: University of Manchester Academic Phrasebank.");
  const aprkbGroupTitle = page.locator("h3").filter({ hasText: "AP-RKB patterns" });
  await expect(aprkbGroupTitle).toHaveCount(1);
  await expect(page.locator('[data-slot="badge"]')).toHaveCount(0);
  await page.screenshot({ path: `${screenshots}/phrasebank-search-all-sources-v2.png`, fullPage: true });
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
  await expect(page.getByRole("status").filter({ hasText: "Manchester reference phrases are unavailable" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Source filter" })).toHaveText("All sources");
});

test("Section and Intent filters show active values and can be cleared", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  await selectFilter(page, "Section filter", "Introduction");
  await expect(page.getByRole("link", { name: /Section One/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Function One/ })).toHaveCount(0);
  const activeFilters = page.getByRole("status", { name: "Active filters" });
  await expect(activeFilters).toContainText("Section: Introduction");
  await expect(page.getByText(/items have no mapping/)).toHaveCount(0);
  await selectFilter(page, "Intent filter", "Invented intent");
  await expect(page.getByRole("link", { name: /Section One/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Function One/ })).toHaveCount(0);
  await expect(activeFilters).toContainText("Intent: Invented intent");
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByRole("combobox", { name: "Section filter" })).toContainText("All sections");
  await expect(page.getByRole("combobox", { name: "Intent filter" })).toContainText("All intents");
  await expect(activeFilters).toHaveCount(0);

  await selectFilter(page, "Intent filter", "All intents");
  await selectFilter(page, "Section filter", "Results");
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("alpha");
  await expect(page.getByText("No Manchester reference results", { exact: true })).toBeVisible();
  await expect(page.getByRole("status", { name: "Active filters" })).toBeVisible();
  await expect(page.getByText(/items have no mapping/)).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("");

  await selectFilter(page, "Section filter", "Introduction");
  await selectFilter(page, "Source filter", "AP-RKB patterns");
  await patternGroup(page, "INTRO · Invented intent").locator("summary").click();
  await expect(page.getByRole("link", { name: "Use in writer" })).toBeVisible();
  await selectFilter(page, "Section filter", "Results");
  await expect(page.getByRole("link", { name: "Use in writer" })).toHaveCount(0);
});

test("combined filters refetch both sources instead of searching their initial capped cache", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  const latePattern = { ...patterns[0]!, id: "late-pattern", canonical_frame: "Needle beyond the original pattern cap" };
  const lateReference = { ...search.results[0]!, entry: { ...search.results[0]!.entry, id: "late-reference", cells: [["Needle beyond the original reference cap"]] } };
  const matches = (params: URLSearchParams) => params.get("q") === "needle"
    && params.get("section") === "INTRO" && params.get("intent") === "INTRO_GAP_INDICATE";
  await page.route("**/v1/patterns**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(matches(params) ? [latePattern] : []) });
  });
  await page.route("**/v1/reference-library/search**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...search, results: matches(params) && params.get("phrase_only") === "true" ? [lateReference] : [] }) });
  });
  await page.goto("/phrasebank");
  await expect(page.getByRole("link", { name: latePattern.canonical_frame })).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("needle");
  await selectFilter(page, "Section filter", "Introduction");
  await selectFilter(page, "Intent filter", "Invented intent");
  await patternGroup(page, "INTRO · Invented intent").locator("summary").click();
  await expect(page.getByRole("link", { name: latePattern.canonical_frame })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Needle beyond the original reference cap" })).toBeVisible();
  await expect(page.getByText(/Showing up to/)).toHaveCount(0);
  await expect(page.getByRole("status", { name: "Active filters" })).toContainText("Section: Introduction");
  await selectFilter(page, "Intent filter", "All intents");
  await expect(page.getByRole("link", { name: latePattern.canonical_frame })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "Needle beyond the original reference cap" })).toHaveCount(0);
});

test("an empty reference source after purge leaves the page and AP-RKB source available", async ({ page }) => {
  await authenticate(page);
  await page.route("**/v1/taxonomy", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(taxonomy) }));
  await page.route("**/v1/reference-library/categories", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ source: null, categories: [] }) }));
  await page.route("**/v1/reference-library/search**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ source: null, query: "invented", results: [] }) }));
  await page.route("**/v1/patterns**", (route) => {
    const isDetail = new URL(route.request().url()).pathname.endsWith("/pattern-1");
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(isDetail ? patterns[0] : patterns) });
  });
  await page.goto("/phrasebank");
  await expect(cardTitle(page, "Sections")).toBeVisible();
  await expect(cardTitle(page, "General functions")).toBeVisible();
  await patternGroup(page, "INTRO · Invented intent").locator("summary").click();
  await expect(page.getByRole("link", { name: "Use in writer" })).toBeVisible();
  await expect(page.getByText(/Manchester reference is disabled/)).toHaveCount(0);
});

test("AP-RKB category shows the Writer cross link", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank/aprkb-patterns");
  await patternGroup(page, "INTRO · Invented intent").locator("summary").click();
  await expect(page.getByText("Alpha invented {topic} frame")).toBeVisible();
  await expect(page.locator('[data-slot="badge"]')).toHaveCount(0);
  await expect(page.getByText(sourceCredit, { exact: true })).toHaveCount(0);
  const writerLink = page.getByRole("link", { name: "Use in writer" });
  await expect(writerLink).toHaveAttribute("href", /\/writer\?/);
  const writerUrl = new URL((await writerLink.getAttribute("href"))!, baseURL);
  expect(writerUrl.pathname).toBe("/writer");
  expect(writerUrl.searchParams.get("intent")).toBe("INTRO_GAP_INDICATE");
  expect(writerUrl.searchParams.get("section")).toBe("INTRO");
  expect(writerUrl.searchParams.get("genre")).toBe("RESEARCH_ARTICLE");
});

test("AP-RKB list opens a complete pattern detail without per-row detail requests", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  let detailRequests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/v1/patterns/pattern-1") detailRequests += 1;
  });
  await page.goto("/phrasebank/aprkb-patterns");
  await patternGroup(page, "INTRO · Invented intent").locator("summary").click();
  await expect(page.getByText("Alpha invented {topic} frame")).toBeVisible();
  expect(detailRequests).toBe(0);
  await page.getByRole("link", { name: "Alpha invented {topic} frame" }).click();
  await expect(page).toHaveURL(/\/phrasebank\/pattern\/pattern-1$/);
  await expect(cardTitle(page, "Frame")).toBeVisible();
  await expect(cardTitle(page, "Slots")).toBeVisible();
  await expect(page.getByText("Type:").first()).toBeVisible();
  await expect(page.getByText("topic", { exact: true })).toBeVisible();
  await expect(page.getByText("Required", { exact: true })).toBeVisible();
  await expect(page.getByText("How to fill:")).toBeVisible();
  await expect(page.getByText("Invented alternative {topic}")).toBeVisible();
  await expect(page.getByText("single_study")).toBeVisible();
  await expect(page.getByText("DISCUSSION")).toBeVisible();
  await expect(page.getByText("Not labelled")).toHaveCount(2);
  await expect(page.getByText(/Creative Commons Attribution/)).toBeVisible();
  await expect(page.getByText("article-1")).toBeVisible();
  await expect(page.getByText("Version 1", { exact: false })).toBeVisible();
  expect(detailRequests).toBe(1);
});

test.beforeAll(() => mkdirSync(screenshots, { recursive: true }));
