import { expect, test, type Page } from "@playwright/test";
import { authenticateCurator } from "./support/auth";

// Real API + PostgreSQL. Start scripts/manual/online_ranking_live_server.py,
// then Vite with VITE_API_PROXY_TARGET=http://127.0.0.1:8016.
test.skip(process.env.ONLINE_RANKING_LIVE !== "1", "Requires the isolated online-ranking live fixture server");
test.use({
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

async function select(page: Page, name: string, label: string) {
  await page.getByRole("combobox", { name, exact: true }).click();
  await page.getByRole("option", { name: label, exact: true }).click();
}

test("move-only request, normalized retrieval, explanations and render use the live API", async ({ page, request }) => {
  const key = await authenticateCurator(page, request);
  const taxonomyResponse = await request.get("/v1/taxonomy", { headers: { "X-API-Key": key } });
  expect(taxonomyResponse.ok()).toBeTruthy();
  const taxonomy = await taxonomyResponse.json();
  const section = taxonomy.sections.find((s: { code: string }) => s.code === "INTRO");
  const move = section.moves.find((m: { steps: { intents: { code: string }[] }[] }) =>
    m.steps.some((s) => s.intents.some((i) => i.code === "INTRO_GAP_INDICATE")));
  await page.goto("/writer");
  await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toBeVisible();
  await select(page, "Manuscript section", section.name);
  await select(page, "Rhetorical move", move.name);
  await expect(page.getByRole("combobox", { name: "Rhetorical intent", exact: true })).toContainText("Any intent");
  await page.getByLabel("Search keywords").fill("suggests");
  const pending = page.waitForResponse((response) => response.url().endsWith("/v1/recommendations") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Find patterns" }).click();
  const response = await pending;
  expect(response.request().postDataJSON()).toMatchObject({ move: move.code, intent: null, query: "suggests" });
  const body = await response.json();
  const candidate = body.items.find((i: { canonical_frame: string }) => i.canonical_frame === "We suggest {topic}.");
  expect(candidate).toBeDefined();
  expect(candidate.breakdown.intent).toBe(0.7);
  expect(candidate.breakdown.linguistic).toBe(1);
  expect(body.fallback_trace.at(-1).tier).toBe("generic_genre");
  expect(candidate.explanation_details.filter((d: { available: boolean }) => d.available)
    .reduce((sum: number, d: { weight: number }) => sum + d.weight, 0)).toBeCloseTo(1);
  await page.getByRole("radio", { name: "Select We suggest {topic}.", exact: true }).click();
  const row = page.getByRole("row").filter({ has: page.getByText("We suggest {topic}.", { exact: true }) });
  await row.getByText("Why this suggestion", { exact: true }).click();
  await expect(row.getByText(/Intent: 0.700 · .*% weight/)).toBeVisible();
  await page.getByRole("textbox", { name: /^\{topic\}/ }).fill("a careful interpretation");
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByLabel("Draft sentence")).toHaveValue("We suggest a careful interpretation.");
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText(/^Claim check/)).toBeVisible();
  // Parent changes invalidate the previous selection and clear child filters.
  await select(page, "Manuscript section", "Results");
  await expect(page.getByRole("combobox", { name: "Rhetorical move", exact: true })).toContainText("Any move");
  await expect(page.getByRole("combobox", { name: "Rhetorical intent", exact: true })).toContainText("Any intent");
  await expect(page.getByRole("radiogroup", { name: "Recommended patterns" })).toHaveCount(0);
});

test("phrasebank carries AP-RKB context to Writer and obtains a fresh recommendation", async ({ page, request }) => {
  const key = await authenticateCurator(page, request);
  const patternsResponse = await request.get("/v1/patterns?status=approved", { headers: { "X-API-Key": key } });
  expect(patternsResponse.ok()).toBeTruthy();
  const patterns = await patternsResponse.json();
  const pattern = patterns.find((p: { canonical_frame: string }) => p.canonical_frame === "We suggest {topic}.");
  await page.goto(`/phrasebank/pattern/${pattern.id}`);
  await expect(page.getByText("We suggest {topic}.", { exact: true })).toBeVisible();
  const pending = page.waitForResponse((response) => response.url().endsWith("/v1/recommendations") && response.request().method() === "POST");
  await page.getByRole("link", { name: "Use in writer", exact: true }).click();
  const response = await pending;
  expect(response.ok()).toBeTruthy();
  expect(response.request().postDataJSON()).toMatchObject({ intent: pattern.intent_code, move: pattern.move_code });
  await expect(page.getByRole("combobox", { name: "Rhetorical intent", exact: true })).toContainText(pattern.intent_name);
  const result = await response.json();
  expect(result.items.every((item: { breakdown: { intent: number } }) => item.breakdown.intent === 1)).toBeTruthy();
  expect(result.recommendation_id).toBeTruthy();
});
