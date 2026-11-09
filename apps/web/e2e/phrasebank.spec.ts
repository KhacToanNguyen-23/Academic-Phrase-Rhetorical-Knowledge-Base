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

async function mockEmptyAcademic(page: Page) {
  await page.route("**/v1/academic-phrases**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = /\/(functions|pragmatic-features|domains)$/.test(path)
      ? { items: [] }
      : { items: [], total: 0, limit: 200, offset: 0 };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

async function mockLibrary(page: Page) {
  await mockEmptyAcademic(page);
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

const academicPhrase = {
  id: "apb-phrase-1", status: "proposed", intent_code: "INTRO_GAP_INDICATE", intent_name: "Indicating a gap",
  canonical_frame: "The role of {topic} in {context} remains underexplored.", version_no: 1, current_version_id: "apb-version-1",
  slots: { topic: { type: "research_topic", label: "Research topic", instruction: "Name a bounded topic", example: "federated learning", required: true }, context: "research_context" },
  variants: [], allowed_sections: ["INTRO"], allowed_genres: ["RESEARCH_ARTICLE"], move_code: "INTRO_GAP",
  communicative_functions: [{ code: "INDICATE_GAP", label: "Indicating a gap", family_code: "IDENTIFYING_NICHE", family_label: "Establishing a niche", purpose: "Show what remains unknown", status: "proposed", version: "1.0.0" }],
  move_links: [{ section_code: "INTRO", code: "INTRO_GAP", label: "Establishing a niche", relation: "REALIZES_MOVE" }],
  step_links: [{ section_code: "INTRO", move_code: "INTRO_GAP", code: "INTRO_INDICATE", label: "Indicating a gap", relation: "REALIZES_STEP" }],
  usage_profiles: [{ section_code: "INTRO", section_label: "Introduction", genre_code: "RESEARCH_ARTICLE", language_code: "en", register_code: "REGISTER_FORMAL_ACADEMIC", discipline_code: "SCI", audience: "Researchers", preferred_usage: "general" }],
  pragmatic_tags: [{ code: "STANCE_EPISTEMIC", version: "1.0.0", label: "Epistemic stance", facet: "stance_type", context_note: "Use for a bounded literature gap.", strength_note: null }],
  examples: [
    { kind: "positive", text: "The role of federated learning in intermittent networks remains underexplored.", explanation: "Names a bounded research context.", origin_kind: "illustrative_synthetic", license_code: null, license_allows_display: true, source_ref: null },
    { kind: "negative", text: "Everything about this topic is unexplored.", explanation: "Overstates the gap.", origin_kind: "illustrative_synthetic", license_code: null, license_allows_display: true, source_ref: null },
  ],
  caveats: [{ code: "GAP_REQUIRES_REVIEW", severity: "warning", message: "Support a gap claim with a documented literature review." }],
  source_type: "original", license_code: "CC-BY", license_name: "Creative Commons Attribution", license_allows_display: true,
  license_flag: false, source_reference: null, article_id: null, source_sentence_count: 0,
  discipline_affinities: [], epistemic_strength: null, epistemic_strength_labelled: false, claim_type: null, claim_type_labelled: false,
  evidence_min: null, forbidden_contexts: [],
};

async function mockAcademicPhraseBank(page: Page) {
  const functions = [{ code: "INDICATE_GAP", family_code: "IDENTIFYING_NICHE", family_label: "Establishing a niche", label: "Indicating a gap", purpose: "Show what remains unknown", status: "proposed", version: "1.0.0" }];
  const features = [
    { code: "STANCE_EPISTEMIC", description: null, facet: "stance_type", label: "Epistemic stance", status: "proposed", version: "1.0.0" },
    { code: "REGISTER_FORMAL_ACADEMIC", description: null, facet: "register", label: "Formal academic", status: "proposed", version: "1.0.0" },
  ];
  const domains = [{ code: "SCI", label: "Science", version: "1.0.0" }];
  await page.route("**/v1/academic-phrases**", (route) => {
    const url = new URL(route.request().url());
    const detailRequest = url.pathname.endsWith("/apb-phrase-1");
    if (url.pathname.endsWith("/functions")) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: functions }) });
    if (url.pathname.endsWith("/pragmatic-features")) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: features }) });
    if (url.pathname.endsWith("/domains")) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: domains }) });
    const params = url.searchParams;
    const matches = params.get("function") === "INDICATE_GAP"
      && params.get("function_version") === "1.0.0"
      && params.get("section") === "INTRO"
      && params.get("stance") === "STANCE_EPISTEMIC"
      && params.get("register") === "REGISTER_FORMAL_ACADEMIC"
      && params.get("domain") === "SCI"
      && params.get("q") === "underexplored";
    if (detailRequest) return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(academicPhrase) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: matches ? [academicPhrase] : [], total: matches ? 1 : 0, limit: 50, offset: 0 }) });
  });
}

// The redesigned filters are Radix comboboxes, not native <select> elements.
async function selectFilter(page: Page, name: string, option: string) {
  await page.getByRole("combobox", { name, exact: true }).click();
  await page.getByRole("option").filter({ hasText: option }).click();
  await expect(page.getByRole("combobox", { name, exact: true })).toContainText(option);
}

function cardTitle(page: Page, text: string) {
  return page.locator('[data-slot="card-title"]').filter({ hasText: new RegExp(`^${text}$`) });
}
function patternGroup(page: Page, title: string) {
  return page.locator("details").filter({ has: page.locator("summary").filter({ hasText: title }) });
}

const resultRows = (page: Page) => page.getByRole("table", { name: "Phrasebank results" }).locator("tbody tr");

test("home shows one unified results table and narrows it by source", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  await expect(page.getByRole("heading", { name: "Phrasebank", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Source filter" })).toContainText("All Phrasebank");
  await expect(page.getByRole("table", { name: "Phrasebank results" }).getByRole("columnheader")).toHaveText(
    ["#", "Name", "Phrase / description", "Section", "Source", ""],
  );
  await expect(resultRows(page)).toHaveCount(3);
  await expect(resultRows(page).filter({ hasText: "Section One" }).getByText("Manchester reference")).toBeVisible();
  await expect(resultRows(page).filter({ hasText: "Function One" })).toHaveCount(1);
  await expect(resultRows(page).filter({ hasText: "Alpha invented {topic} frame" }).getByText("AP-RKB patterns")).toBeVisible();
  await expect(page.getByText(sourceCredit, { exact: true })).toHaveCount(1);
  await page.screenshot({ path: `${screenshots}/phrasebank-home-v2.png`, fullPage: true });
  await selectFilter(page, "Source filter", "Manchester reference");
  await expect(resultRows(page)).toHaveCount(2);
  await expect(page.getByText("Alpha invented {topic} frame")).toHaveCount(0);
  await selectFilter(page, "Source filter", "AP-RKB patterns");
  await expect(resultRows(page)).toHaveCount(1);
  await expect(page.getByText(sourceCredit, { exact: true })).toHaveCount(0);
  await resultRows(page).first().getByRole("link", { name: "View" }).click();
  await expect(page).toHaveURL(/\/phrasebank\/pattern\/pattern-1$/);
  expect(consoleErrors.filter((message) => /unique "key" prop|cannot be given refs/i.test(message))).toEqual([]);
});

test("APB combines server filters and renders full phrase detail with examples and caveats", async ({ page }) => {
  const apbApiKeys: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/v1/academic-phrases")) {
      apbApiKeys.push(request.headers()["x-api-key"] ?? "");
    }
  });
  await authenticate(page);
  await mockLibrary(page);
  await mockAcademicPhraseBank(page);
  await page.goto("/phrasebank");
  await selectFilter(page, "Source filter", "Academic Phrase Bank");
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("underexplored");
  await selectFilter(page, "Section filter", "Introduction");
  await selectFilter(page, "APB function filter", "Indicating a gap");
  // Stance, register and domain live in the "More filters" popover.
  await page.getByRole("button", { name: /More filters/ }).first().click();
  await selectFilter(page, "APB stance filter", "Epistemic stance");
  await selectFilter(page, "APB register filter", "Formal academic");
  await selectFilter(page, "APB domain filter", "Science");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("status", { name: "Active APB filters" })).toContainText("Indicating a gap");
  await expect(resultRows(page)).toHaveCount(1);
  await expect(resultRows(page).first()).toContainText("The role of {topic}");
  expect(apbApiKeys.length).toBeGreaterThan(0);
  expect(apbApiKeys.every((key) => key === "test-staff-key")).toBe(true);
  await resultRows(page).first().getByRole("link", { name: "View" }).click();
  await expect(page).toHaveURL(/\/phrasebank\/apb\/apb-phrase-1$/);
  await expect(page.getByText("Positive examples")).toBeVisible();
  await expect(page.getByText("Negative examples")).toBeVisible();
  await expect(page.getByText("GAP_REQUIRES_REVIEW")).toHaveCount(0);
  await expect(page.getByText("Support a gap claim with a documented literature review.")).toBeVisible();
  await expect(page.getByText("VTB Concept/Sense")).toBeVisible();
  await expect(page.getByText("display permitted").first()).toBeVisible();
});

test("an active APB facet limits the table to Academic Phrase Bank and says why", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  await mockAcademicPhraseBank(page);
  await page.goto("/phrasebank");
  await expect(resultRows(page)).toHaveCount(3);
  await page.getByRole("button", { name: /More filters/ }).first().click();
  await selectFilter(page, "APB stance filter", "Epistemic stance");
  await page.keyboard.press("Escape");
  await expect(page.getByText(/only apply to Academic Phrase Bank/)).toBeVisible();
  await expect(page.getByText("Alpha invented {topic} frame")).toHaveCount(0);
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

test("search lists Manchester and AP-RKB matches in one table and opens the category heading", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 480 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  const searchBox = page.getByRole("searchbox", { name: "Search phrasebanks" });
  await expect(searchBox).toBeVisible();
  await searchBox.fill("alpha");
  await expect(resultRows(page)).toHaveCount(3);
  const reference = resultRows(page).filter({ hasText: "Manchester reference" });
  await expect(reference).toHaveCount(2);
  await expect(reference.first()).toContainText("Alpha beta / beta");
  await expect(reference.first().locator("mark")).toHaveText("Alpha");
  await expect(reference.first().getByRole("button", { name: "Open heading" })).toBeVisible();
  await expect(resultRows(page).filter({ hasText: "AP-RKB patterns" })).toHaveCount(1);
  await expect(page.getByText("Final note")).toHaveCount(0);
  await expect(page.getByText("Intro note")).toHaveCount(0);
  await expect(page.getByText(sourceCredit, { exact: true })).toBeVisible();
  await page.screenshot({ path: `${screenshots}/phrasebank-search-all-sources-v2.png`, fullPage: true });
  await reference.first().getByRole("button", { name: "Open heading" }).click();
  await expect(page).toHaveURL(/\/phrasebank\/section-one#heading-section-one-1$/);
  await expect.poll(() => page.locator("#heading-section-one-1").evaluate((element) => {
    const { top } = element.getBoundingClientRect();
    return window.scrollY > 0 && top >= 0 && top < window.innerHeight;
  })).toBe(true);
});

test("disabled Manchester collection displays its disabled state", async ({ page }) => {
  await authenticate(page);
  await mockEmptyAcademic(page);
  await page.route("**/v1/reference-library/**", (route) => route.fulfill({
    status: 404, contentType: "application/json",
    body: JSON.stringify({ error: { code: "NOT_FOUND", message: "Reference library is disabled", details: null }, request_id: "test" }),
  }));
  await page.route("**/v1/patterns**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.goto("/phrasebank");
  await expect(page.getByRole("status").filter({ hasText: "Manchester reference phrases are unavailable" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Source filter" })).toContainText("All Phrasebank");
});

test("Section and Intent filters show active values and can be cleared", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  await page.goto("/phrasebank");
  await selectFilter(page, "Section filter", "Introduction");
  await expect(resultRows(page).filter({ hasText: "Section One" })).toHaveCount(1);
  await expect(resultRows(page).filter({ hasText: "Function One" })).toHaveCount(0);
  const activeFilters = page.getByRole("status", { name: "Active APB filters" });
  await expect(activeFilters).toContainText("Section: Introduction");
  await selectFilter(page, "Intent filter", "Invented intent");
  await expect(resultRows(page).filter({ hasText: "Section One" })).toHaveCount(1);
  await expect(resultRows(page).filter({ hasText: "Function One" })).toHaveCount(0);
  await expect(activeFilters).toContainText("Intent: Invented intent");
  await page.getByRole("button", { name: "Clear all" }).click();
  await expect(page.getByRole("combobox", { name: "Section filter" })).toContainText("All sections");
  await expect(page.getByRole("combobox", { name: "Intent filter" })).toContainText("All intents");
  await expect(activeFilters).toHaveCount(0);

  await selectFilter(page, "Section filter", "Results");
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("alpha");
  await expect(page.getByText("No phrases match", { exact: true })).toBeVisible();
  await expect(activeFilters).toBeVisible();
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("");

  await selectFilter(page, "Section filter", "Introduction");
  await selectFilter(page, "Source filter", "AP-RKB patterns");
  await expect(page.getByRole("cell", { name: "Alpha invented {topic} frame" })).toBeVisible();
  await selectFilter(page, "Section filter", "Results");
  await expect(page.getByRole("cell", { name: "Alpha invented {topic} frame" })).toHaveCount(0);
});

test("combined filters refetch every source instead of searching a cached page", async ({ page }) => {
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
  await expect(page.getByRole("cell", { name: latePattern.canonical_frame })).toHaveCount(0);
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("needle");
  await selectFilter(page, "Section filter", "Introduction");
  await selectFilter(page, "Intent filter", "Invented intent");
  await expect(page.getByRole("cell", { name: latePattern.canonical_frame })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Needle beyond the original reference cap" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Active APB filters" })).toContainText("Section: Introduction");
  await selectFilter(page, "Intent filter", "All intents");
  await expect(page.getByRole("cell", { name: latePattern.canonical_frame })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "Needle beyond the original reference cap" })).toHaveCount(0);
});

test("results are paginated, reach patterns beyond the API cap and reset for new filters", async ({ page }) => {
  await authenticate(page);
  await mockLibrary(page);
  const catalog = Array.from({ length: 250 }, (_, index) => ({
    ...patterns[0]!,
    id: `page-pattern-${index + 1}`,
    canonical_frame: `${index < 100 ? "Alpha" : "Beta"} pattern ${index + 1}`,
    allowed_sections: [index < 50 ? "RESULTS" : "INTRO"],
    slots: index % 2 === 0 ? patterns[0]!.slots : {},
  }));
  await page.route("**/v1/patterns?**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    const offset = Number(params.get("offset"));
    const limit = Number(params.get("limit"));
    const hasSlots = params.get("has_slots");
    const matches = catalog.filter((item) =>
      item.canonical_frame.toLowerCase().includes(params.get("q") ?? "")
      && (!params.get("section") || item.allowed_sections.includes(params.get("section")!))
      && (hasSlots === null || (Object.keys(item.slots).length > 0) === (hasSlots === "true")));
    return route.fulfill({ json: matches.slice(offset, offset + limit) });
  });

  await page.goto("/phrasebank");
  await selectFilter(page, "Source filter", "AP-RKB patterns");
  const pager = page.getByRole("navigation", { name: "Results pagination" });
  const previous = pager.getByRole("button", { name: "Previous page" });
  const next = pager.getByRole("button", { name: "Next page" });
  const summary = page.getByRole("status").filter({ hasText: /^Showing \d/ });
  await expect(summary).toHaveText("Showing 1–20 of 250 results.");
  await expect(previous).toBeDisabled();
  await expect(resultRows(page)).toHaveCount(20);
  for (let pageNumber = 2; pageNumber <= 13; pageNumber++) {
    await next.click();
    await expect(pager).toContainText(`Page ${pageNumber} of 13`);
  }
  await expect(page.getByRole("cell", { name: "Beta pattern 250", exact: true })).toBeVisible();
  await expect(next).toBeDisabled();
  await previous.click();
  await expect(pager).toContainText("Page 12 of 13");

  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("alpha");
  await expect(pager).toContainText("Page 1 of 5");
  await expect(summary).toHaveText("Showing 1–20 of 100 results.");
  await expect(page.getByRole("cell", { name: "Alpha pattern 1", exact: true })).toBeVisible();

  await selectFilter(page, "Fill-in fields", "Has fill-in fields");
  await expect(summary).toHaveText("Showing 1–20 of 50 results.");
  await expect(page.getByRole("cell", { name: "Alpha pattern 1", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Alpha pattern 2", exact: true })).toHaveCount(0);
  await selectFilter(page, "Fill-in fields", "No fill-in fields");
  await expect(page.getByRole("cell", { name: "Alpha pattern 2", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Alpha pattern 1", exact: true })).toHaveCount(0);
  await selectFilter(page, "Fill-in fields", "All phrases");
  await selectFilter(page, "Section filter", "Introduction");
  await expect(summary).toHaveText("Showing 1–20 of 50 results.");
  await expect(page.getByRole("cell", { name: "Alpha pattern 51", exact: true })).toBeVisible();
});

test("long selected intent stays within the filter card", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await authenticate(page);
  await mockLibrary(page);
  const longIntent = "Describing the process: participant tasks and the specific instructions given to participants in each study group";
  const taxonomyWithLongIntent = JSON.parse(JSON.stringify(taxonomy)) as typeof taxonomy;
  taxonomyWithLongIntent.sections[0]!.moves[0]!.steps[0]!.intents[0]!.name = longIntent;
  await page.route("**/v1/taxonomy", (route) => route.fulfill({ json: taxonomyWithLongIntent }));

  await page.goto("/phrasebank");
  await selectFilter(page, "Intent filter", longIntent);
  const intent = page.getByRole("combobox", { name: "Intent filter" });
  await expect(intent).toHaveAttribute("title", longIntent);
  const intentText = intent.getByText(longIntent, { exact: true });
  const search = page.getByRole("searchbox", { name: "Search phrasebanks" });
  for (const width of [1024, 1440]) {
    await page.setViewportSize({ width, height: 768 });
    const intentBox = (await intent.boundingBox())!;
    const searchBox = (await search.boundingBox())!;
    const cardBox = (await intent.locator("xpath=ancestor::div[@data-slot='card'][1]").boundingBox())!;
    expect(intentBox.x + intentBox.width).toBeLessThanOrEqual(cardBox.x + cardBox.width);
    expect(intentBox.y).toBeGreaterThanOrEqual(searchBox.y + searchBox.height);
    await expect(intentText).toHaveCSS("text-overflow", "ellipsis");
    expect(await intentText.evaluate((element) => element.scrollWidth > element.clientWidth)).toBe(true);
  }
});

test("an empty reference source after purge leaves the page and AP-RKB source available", async ({ page }) => {
  await authenticate(page);
  await mockEmptyAcademic(page);
  await page.route("**/v1/taxonomy", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(taxonomy) }));
  await page.route("**/v1/reference-library/categories", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ source: null, categories: [] }) }));
  await page.route("**/v1/reference-library/search**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ source: null, query: "invented", results: [] }) }));
  await page.route("**/v1/patterns**", (route) => {
    const isDetail = new URL(route.request().url()).pathname.endsWith("/pattern-1");
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(isDetail ? patterns[0] : patterns) });
  });
  await page.goto("/phrasebank");
  await expect(resultRows(page)).toHaveCount(1);
  await expect(page.getByRole("cell", { name: "Alpha invented {topic} frame" })).toBeVisible();
  await expect(page.getByText(/Manchester reference.*unavailable/)).toHaveCount(0);
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
