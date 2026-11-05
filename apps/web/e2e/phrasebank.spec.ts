import { mkdirSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

const screenshots = process.env.E2E_SCREENSHOT_DIR ?? "test-results/phrasebank-screens";
const sourceCredit = "Source: Lab-authored Phrasebank Basic.";
const taxonomy = {
  release_id: "release-fixture", version: "0.2.0",
  sections: [
    { id: "section-methods", code: "METHODS", name: "Methods", order: 1, moves: [
      { id: "move-fixture", code: "METHODS_MOVE", name: "Invented move", steps: [
        { id: "step-fixture", code: "METHODS_STEP", name: "Invented step", intents: [
          { id: "intent-fixture", code: "METHODS_FIXTURE", name: "Invented method intent", description: null },
        ] },
      ] },
    ] },
    { id: "section-results", code: "RESULTS", name: "Results", order: 2, moves: [] },
  ],
  article_genres: [],
};
const pattern = {
  id: "pattern-1", status: "approved", intent_code: "METHODS_FIXTURE",
  canonical_frame: "Alpha invented {topic} frame", intent_name: "Invented method intent",
  version_no: 1, current_version_id: "version-1",
  slots: { topic: { type: "topic", label: "Topic", instruction: "Name an invented topic", example: "invented method", required: true, min_length: 1 } },
  epistemic_strength: null, epistemic_strength_labelled: false,
  claim_type: null, claim_type_labelled: false,
  variants: [{ text: "Invented alternative {topic}", register: "formal" }],
  evidence_min: "single_study", forbidden_contexts: ["DISCUSSION"],
  allowed_sections: ["METHODS"], allowed_genres: ["RESEARCH_ARTICLE"],
  source_type: "authored", license_code: null, license_name: null,
  license_allows_display: false, license_flag: false, article_id: null, source_reference: null,
  source_sentence_count: 0, discipline_affinities: [],
};

test.use({
  baseURL: process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173",
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

async function select(page: Page, name: string, option: string) {
  await page.getByRole("combobox", { name, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

async function mockLibrary(page: Page) {
  const referenceRequests: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/v1/reference-library")) {
      referenceRequests.push(request.url());
    }
  });
  await page.addInitScript(() => sessionStorage.setItem("aprkb-staff-session", "test-staff-key"));
  await page.route("**/v1/auth/me", (route) => route.fulfill({
    json: { id: "test-id", name: "Test curator", role: "curator" },
  }));
  await page.route("**/v1/taxonomy", (route) => route.fulfill({ json: taxonomy }));
  await page.route("**/v1/reference-library/**", (route) => route.fulfill({
    status: 404, json: { error: { code: "NOT_FOUND", message: "Reference library is disabled" } },
  }));
  await page.route("**/v1/patterns**", (route) => {
    const url = new URL(route.request().url());
    const params = url.searchParams;
    const matches = (!params.get("section") || pattern.allowed_sections.includes(params.get("section")!))
      && (!params.get("intent") || pattern.intent_code === params.get("intent"))
      && (!params.get("q") || pattern.canonical_frame.toLowerCase().includes(params.get("q")!.toLowerCase()));
    return route.fulfill({ json: url.pathname.endsWith("/pattern-1") ? pattern : matches ? [pattern] : [] });
  });
  return referenceRequests;
}

test("home shows lab-authored patterns without requesting the external reference library", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  const referenceRequests = await mockLibrary(page);
  await page.goto("/phrasebank");
  await expect(page.getByRole("heading", { name: "Phrasebank", exact: true })).toBeVisible();
  await expect(page.getByText("Lab Phrasebank Basic", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "METHODS · Invented method intent" })).toBeVisible();
  await expect(page.getByRole("link", { name: pattern.canonical_frame })).toBeVisible();
  await expect(page.getByRole("link", { name: "Use in writer" })).toHaveAttribute("href", "/writer");
  await expect(page.getByText(sourceCredit, { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Source filter" })).toHaveCount(0);
  expect(referenceRequests).toEqual([]);
  expect(consoleErrors.filter((message) => /unique "key" prop/i.test(message))).toEqual([]);
  await page.screenshot({ path: `${screenshots}/phrasebank-home.png`, fullPage: true });
});

test("section and intent filters refetch approved lab patterns and can be cleared", async ({ page }) => {
  await mockLibrary(page);
  await page.goto("/phrasebank");
  await select(page, "Section filter", "Methods");
  await select(page, "Intent filter", "Invented method intent");
  await expect(page.getByRole("link", { name: pattern.canonical_frame })).toBeVisible();
  await select(page, "Section filter", "Results");
  await expect(page.getByText("No approved AP-RKB patterns match", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Use in writer" })).toHaveCount(0);
  await select(page, "Section filter", "All sections");
  await select(page, "Intent filter", "All intents");
  await expect(page.getByRole("link", { name: pattern.canonical_frame })).toBeVisible();
});

test("combined search filters fetch beyond the initial capped pattern cache", async ({ page }) => {
  const referenceRequests = await mockLibrary(page);
  const requests: URLSearchParams[] = [];
  const late = { ...pattern, id: "late-pattern", canonical_frame: "Needle beyond the original pattern cap" };
  await page.route("**/v1/patterns**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    requests.push(params);
    const matches = params.get("q") === "needle" && params.get("section") === "METHODS"
      && params.get("intent") === pattern.intent_code;
    return route.fulfill({ json: matches ? [late] : [] });
  });
  await page.goto("/phrasebank");
  await expect(page.getByText("No approved AP-RKB patterns match", { exact: true })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search phrasebanks" }).fill("needle");
  await select(page, "Section filter", "Methods");
  await select(page, "Intent filter", "Invented method intent");
  await expect(page.getByRole("link", { name: late.canonical_frame })).toBeVisible();
  await expect(page.getByText("Showing up to 200 AP-RKB matching results.")).toBeVisible();
  expect(requests.some((params) => params.get("status") === "approved" && params.get("limit") === "200"
    && params.get("q") === "needle" && params.get("section") === "METHODS"
    && params.get("intent") === pattern.intent_code)).toBe(true);
  await select(page, "Intent filter", "All intents");
  await expect(page.getByRole("link", { name: late.canonical_frame })).toHaveCount(0);
  expect(referenceRequests).toEqual([]);
});

test("external category routes are unavailable without fetching external data", async ({ page }) => {
  const referenceRequests = await mockLibrary(page);
  await page.goto("/phrasebank/section-one");
  await expect(page.getByText("Phrasebank category not found", { exact: true })).toBeVisible();
  await expect(page.getByText("Only lab-authored Phrasebank Basic categories are available in Online.")).toBeVisible();
  expect(referenceRequests).toEqual([]);
});

test("lab category shows its source and Writer cross link", async ({ page }) => {
  const referenceRequests = await mockLibrary(page);
  await page.goto("/phrasebank/aprkb-patterns");
  await expect(page.getByRole("heading", { name: "Lab Phrasebank Basic" })).toBeVisible();
  await expect(page.getByRole("link", { name: pattern.canonical_frame })).toBeVisible();
  await expect(page.getByText(sourceCredit, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Use in writer" }).click();
  await expect(page).toHaveURL(/\/writer$/);
  expect(referenceRequests).toEqual([]);
});

test("list opens complete pattern detail with one detail request", async ({ page }) => {
  await mockLibrary(page);
  let detailRequests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/v1/patterns/pattern-1") detailRequests += 1;
  });
  await page.goto("/phrasebank/aprkb-patterns");
  await expect(page.getByRole("link", { name: pattern.canonical_frame })).toBeVisible();
  expect(detailRequests).toBe(0);
  await page.getByRole("link", { name: pattern.canonical_frame }).click();
  await expect(page).toHaveURL(/\/phrasebank\/pattern\/pattern-1$/);
  await expect(page.getByRole("heading", { name: "Frame", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Slots", exact: true })).toBeVisible();
  await expect(page.getByText(/Type: topic; Label: Topic/)).toBeVisible();
  await expect(page.getByText("Invented alternative {topic}")).toBeVisible();
  await expect(page.getByText("single_study")).toBeVisible();
  await expect(page.getByText("DISCUSSION")).toBeVisible();
  await expect(page.getByText("Not labelled")).toHaveCount(2);
  await expect(page.getByText("Version 1", { exact: true })).toBeVisible();
  expect(detailRequests).toBe(1);
});

test("an empty lab collection keeps search and filters available", async ({ page }) => {
  await mockLibrary(page);
  await page.route("**/v1/patterns**", (route) => route.fulfill({ json: [] }));
  await page.goto("/phrasebank");
  await expect(page.getByText("No approved AP-RKB patterns match", { exact: true })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search phrasebanks" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Section filter" })).toBeVisible();
  await expect(page.getByText(sourceCredit, { exact: true })).toBeVisible();
});

test("a failed pattern list can be retried", async ({ page }) => {
  await mockLibrary(page);
  let attempts = 0;
  await page.route("**/v1/patterns**", (route) => {
    attempts += 1;
    return route.fulfill(attempts === 1
      ? { status: 503, json: { error: { code: "UNAVAILABLE", message: "Test service unavailable" } } }
      : { json: [pattern] });
  });
  await page.goto("/phrasebank");
  await expect(page.getByText("Could not load approved patterns", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByRole("link", { name: pattern.canonical_frame })).toBeVisible();
});

test.beforeAll(() => mkdirSync(screenshots, { recursive: true }));
