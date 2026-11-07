import { expect, test, type Page } from "@playwright/test";
import type { ArticleRow, Phrase } from "../src/features/phrase-extraction/types";

test.use({
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

const counts = { pending: 0, accepted: 0, rejected: 0 };
const article = (id: string, mining_status: ArticleRow["mining_status"]): ArticleRow => ({
  id, title: `Article ${id}`, doi: null, journal: null, batch_id: "batch-1",
  ingest_status: "ready", mining_status, phrases: { ...counts },
});
const phrase = (id: number): Phrase => ({
  id: `phrase-${id}`, canonical_frame: `[X] reports that [Y].`, slots: {},
  epistemic_strength: null, status: "pending", blocked: false,
  sources: [{ sentence_id: `sentence-${id}`, article_id: "done", article_title: "Article done",
    journal: null, section: "RESULTS", text: `Our example reports that result ${id} is useful.`, slot_spans: {} }],
});

async function mockExtraction(page: Page, articles: ArticleRow[], initialPhrases: Phrase[] = []) {
  let phrases = initialPhrases;
  await page.addInitScript(() => sessionStorage.setItem("aprkb-staff-session", "test-key"));
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let body: unknown;
    if (path === "/v1/auth/me") {
      body = { id: "reviewer", name: "Test curator", role: "curator" };
    } else if (path === "/v1/admin/corpus/batches") {
      body = [{ batch_id: "batch-1", imported_at: "2026-11-06T00:00:00Z", articles: articles.length,
        ready: articles.length, mined: 1, phrases: { ...counts, pending: phrases.length } }];
    } else if (path === "/v1/admin/corpus/articles") {
      body = articles;
    } else if (path === "/v1/admin/corpus/mine") {
      body = { job_ids: ["job-1", "job-2"], articles: 2, skipped_not_ready: 0 };
    } else if (path.endsWith("/decision")) {
      const id = path.split("/").at(-2)!;
      phrases = phrases.filter((item) => item.id !== id);
      body = { candidate_id: id, status: "accepted", approved_phrase_id: `approved-${id}` };
    } else if (path === "/v1/admin/extraction/phrases") {
      const offset = Number(url.searchParams.get("offset") ?? 0);
      const pending = url.searchParams.get("status") === "pending";
      body = { items: pending ? phrases.slice(offset, offset + 50) : [], total: pending ? phrases.length : 0 };
    } else {
      await route.fulfill({ status: 404, json: { detail: `Unexpected test request: ${path}` } });
      return;
    }
    await route.fulfill({ status: 200, json: body });
  });
  await page.goto("/extract");
}

test("requests only eligible articles and reports job reuse truthfully", async ({ page }) => {
  await mockExtraction(page, [article("done", "succeeded"), article("new", "not_started"), article("retry", "failed")]);
  const request = page.waitForRequest((req) => req.url().endsWith("/v1/admin/corpus/mine") && req.method() === "POST");
  await page.getByRole("button", { name: "Extract 2 article(s)", exact: true }).click();
  expect((await request).postDataJSON()).toEqual({ article_ids: ["new", "retry"], batch_ids: [], unbatched: false });
  await expect(page.getByText("Extraction requested for 2 article(s); existing jobs may be reused.")).toBeVisible();
  await expect(page.getByLabel("Extraction status summary")).toContainText("1 completed · 1 failed");
});

test("distinguishes completed zero matches from an empty review status", async ({ page }) => {
  await mockExtraction(page, [article("done", "succeeded")]);
  await expect(page.getByText("Extraction finished with no matches", { exact: true })).toBeVisible();
  await expect(page.getByText(/The current extractor recognizes a limited set/)).toBeVisible();
  await expect(page.getByText(/They do not automatically become writing suggestions/)).toBeVisible();
});

test("an empty pending tab does not imply extraction found no matches", async ({ page }) => {
  await mockExtraction(page, [{ ...article("done", "succeeded"), phrases: { ...counts, accepted: 1 } }]);
  await expect(page.getByText("No pending phrases", { exact: true })).toBeVisible();
  await expect(page.getByText("Extraction finished with no matches", { exact: true })).toHaveCount(0);
});

test("accepting the last item on page two returns to remaining candidates", async ({ page }) => {
  await mockExtraction(page, [{ ...article("done", "succeeded"), phrases: { ...counts, pending: 51 } }],
    Array.from({ length: 51 }, (_, index) => phrase(index)));
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(page.getByText("51–51 of 51")).toBeVisible();
  await page.getByRole("checkbox", { name: "Select phrase [X] reports that [Y].", exact: true }).check();
  await page.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(page.getByText("Phrase saved to approved phrases.", { exact: true })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Select phrase [X] reports that [Y].", exact: true })).toHaveCount(50);
  await expect(page.getByRole("button", { name: "Accept (1)", exact: true })).toHaveCount(0);
});
