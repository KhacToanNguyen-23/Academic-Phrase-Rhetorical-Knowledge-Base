import { expect, test, type Page } from "@playwright/test";
import { authenticateCurator } from "./support/auth";

// ADR-0015. Catalog and APB pages run against mocked measurement routes, so they do not
// depend on MEASUREMENT_ENABLED in the e2e environment. The Writer test uses the live API
// and mocks only the suggestion route.

const PATTERN_ID = "11111111-1111-4111-8111-111111111111";

const entries = [
  { code: "accuracy", kind: "metric", name: "Accuracy", aliases: ["ACC"], definition: "Share of correct judgements." },
  { code: "likert_5_point", kind: "method", name: "5-point Likert scale questionnaire", aliases: ["5-point Likert"], definition: "Five ordered options." },
  { code: "pre_post_test", kind: "protocol", name: "Pre-test/post-test design", aliases: [], definition: "Measure before and after." },
];

async function mockCatalog(page: Page) {
  await page.route("**/v1/measurements?**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    const kind = params.get("kind");
    const q = (params.get("q") ?? "").toLowerCase();
    const items = entries.filter(
      (item) => (!kind || item.kind === kind)
        && (!q || [item.name, ...item.aliases].some((term) => term.toLowerCase().includes(q))),
    );
    return route.fulfill({ json: { catalog_version: "0.2.0", items, total: items.length } });
  });
}

async function mockCurator(page: Page) {
  await page.addInitScript(() => sessionStorage.setItem("aprkb-web-session", "test-staff-key"));
  await page.route("**/v1/auth/session/me", (route) => route.fulfill({
    json: { id: "test-id", name: "Test curator", role: "curator" },
  }));
}

test("catalog filters by kind and alias and opens an entry", async ({ page }) => {
  await mockCurator(page);
  await mockCatalog(page);
  await page.route("**/v1/measurements/likert_5_point", (route) => route.fulfill({
    json: {
      ...entries[1], formula: null, scale: "5 ordered options", value_range: "1 to 5",
      usage_note: "Ordinal data.", example: "a five-point scale", catalog_version: "0.2.0",
      related: [{ relation: "part_of", direction: "outgoing", code: "pre_post_test", kind: "protocol", name: "Pre-test/post-test design" }],
      slot_links: [{
        id: "link-1", entry_code: "likert_5_point", pattern_id: PATTERN_ID, canonical_frame: "Q2 asked participants to rate X on a 5-point Likert scale.",
        slot_name: null, origin: "term_match", review_status: "approved", note: null, created_at: "2026-11-10T00:00:00Z", reviewed_at: "2026-11-10T00:00:00Z",
      }],
    },
  }));
  await page.route("**/v1/admin/measurements/slot-links?**", (route) => route.fulfill({ json: { items: [] } }));

  await page.goto("/measurements");
  await expect(page.getByText("3 entries · catalog 0.2.0")).toBeVisible();
  // Reading order: metric, method, protocol.
  await expect(page.getByRole("main").getByRole("listitem").first()).toContainText("Accuracy");

  await page.getByRole("tab", { name: "Protocol" }).click();
  await expect(page).toHaveURL(/kind=protocol/);
  await expect(page.getByText("1 entry · catalog 0.2.0")).toBeVisible();
  await page.getByRole("tab", { name: "All" }).click();

  await page.getByRole("searchbox", { name: "Search the measurement catalog" }).fill("5-point");
  await expect(page).toHaveURL(/q=5-point/);
  await expect(page.getByText("1 entry · catalog 0.2.0")).toBeVisible();
  await page.getByRole("link", { name: /5-point Likert scale questionnaire/ }).click();

  await expect(page.getByRole("heading", { name: "5-point Likert scale questionnaire" })).toBeVisible();
  await expect(page.getByText("Part of protocol")).toBeVisible();
  await expect(page.getByText("Whole pattern")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open pattern" })).toHaveAttribute("href", `/phrasebank/pattern/${PATTERN_ID}`);
});

test("curator approves a proposed term-match link on the entry page", async ({ page }) => {
  await mockCurator(page);
  const proposed = {
    id: "link-9", entry_code: "accuracy", pattern_id: PATTERN_ID, canonical_frame: "Accuracy was computed on the test set.",
    slot_name: null, origin: "term_match", review_status: "proposed", note: null, created_at: "2026-11-10T00:00:00Z", reviewed_at: null,
  };
  let pending = [proposed];
  await page.route("**/v1/measurements/accuracy", (route) => route.fulfill({
    json: {
      ...entries[0], formula: "(TP + TN) / N", scale: null, value_range: "0 to 1", usage_note: null,
      example: null, catalog_version: "0.2.0", related: [], slot_links: [],
    },
  }));
  await page.route("**/v1/admin/measurements/slot-links?**", (route) => route.fulfill({ json: { items: pending } }));
  const reviewed = page.waitForRequest((request) => request.url().endsWith("/v1/admin/measurements/slot-links/link-9/review"));
  await page.route("**/v1/admin/measurements/slot-links/link-9/review", (route) => {
    pending = [];
    return route.fulfill({ json: { ...proposed, review_status: "approved", reviewed_at: "2026-11-10T01:00:00Z" } });
  });

  await page.goto("/measurements/accuracy");
  await expect(page.getByText("Proposed links to review")).toBeVisible();
  await expect(page.getByText("Whole pattern · matched catalog term")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  expect((await reviewed).postDataJSON()).toEqual({ decision: "approved" });
  await expect(page.getByText("Proposed links to review")).toHaveCount(0);
});

test("switched-off catalog explains itself instead of failing", async ({ page }) => {
  await mockCurator(page);
  await page.route("**/v1/measurements?**", (route) => route.fulfill({
    status: 404, json: { error: { code: "NOT_FOUND", message: "Measurement catalog is disabled" } },
  }));
  await page.goto("/measurements");
  await expect(page.getByText("Measurement catalog is switched off")).toBeVisible();
});

test("APB pattern page shows approved measurement context only", async ({ page }) => {
  await mockCurator(page);
  await page.route(`**/v1/academic-phrases/${PATTERN_ID}`, (route) => route.fulfill({
    json: {
      id: PATTERN_ID, version_no: 1, canonical_frame: "Reliability was calculated using Cronbach’s alpha.",
      slots: {}, intent_code: "METHODS_STATISTICAL_PROCEDURES", intent_name: "Statistical procedures",
      allowed_sections: ["METHODS"], allowed_genres: [], status: "draft", source_type: "authored",
      communicative_functions: [], move_links: [], step_links: [], usage_profiles: [],
      pragmatic_tags: [], examples: [], caveats: [],
    },
  }));
  await page.route("**/v1/measurements/pattern-measurements?**", (route) => route.fulfill({
    json: {
      pattern_id: PATTERN_ID,
      items: [
        { code: "cronbachs_alpha", kind: "metric", name: "Cronbach's alpha", definition: "Internal consistency.", slot_name: null },
        { code: "likert_5_point", kind: "method", name: "Slot-level only", definition: "Shown under its slot instead.", slot_name: "instrument" },
      ],
    },
  }));

  await page.goto(`/phrasebank/apb/${PATTERN_ID}`);
  const card = page.locator("[data-slot='card']", { hasText: "Measurement context" });
  await expect(card).toBeVisible();
  await expect(card.getByRole("link", { name: "Cronbach's alpha" })).toHaveAttribute("href", "/measurements/cronbachs_alpha");
  await expect(card.getByText("Slot-level only")).toHaveCount(0);
});

test.describe("writer", () => {
  test.use({ baseURL: process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173" });

  test("writer shows reviewed measurement ideas under a slot without filling it", async ({ page, request: api }) => {
    await authenticateCurator(page, api);
    await page.route("**/v1/measurements/slot-suggestions?**", (route) => {
      const slot = new URL(route.request().url()).searchParams.get("slot");
      return route.fulfill({
        json: {
          pattern_id: PATTERN_ID,
          slot_name: slot,
          items: slot === "context"
            ? [{ code: "pre_post_test", kind: "protocol", name: "Pre-test/post-test design", example: null }]
            : [],
          notice: "Suggestions only. The writer must choose and phrase the slot value.",
        },
      });
    });

    await page.goto("/writer");
    await page.getByRole("button", { name: "Find patterns" }).click();
    await page.getByRole("radio", { name: "Select The role of {topic} in {context} remains underexplored." }).click();

    const ideas = page.getByTestId("measurement-ideas-context");
    await expect(ideas).toContainText("Pre-test/post-test design");
    await expect(ideas).toContainText("suggestions only");
    await expect(ideas.getByRole("link")).toHaveCount(0);
    await expect(page.getByTestId("measurement-ideas-topic")).toHaveCount(0);
    await expect(page.getByRole("textbox", { name: /^\{context\}/ })).toHaveValue("");
  });
});
