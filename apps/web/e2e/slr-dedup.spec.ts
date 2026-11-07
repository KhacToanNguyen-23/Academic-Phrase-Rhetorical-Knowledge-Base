import { expect, test } from "@playwright/test";

test.use({
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

test("import result explains confirmed duplicates and title review hints", async ({ page }) => {
  await page.addInitScript(() => {
    sessionStorage.setItem("aprkb-staff-session", "test-staff-key");
    sessionStorage.setItem("aprkb-api-key", "test-corpus-key");
  });
  await page.route("**/v1/auth/me", (route) => route.fulfill({ json: {
    id: "curator", name: "Test curator", role: "curator",
  } }));
  await page.route("**/v1/admin/corpus/sources/slr/taxonomy**", (route) => route.fulfill({ json: { items: [], nextCursor: null } }));
  await page.route("**/v1/admin/corpus/import-profiles", (route) => route.fulfill({ json: [{
    id: "profile-1", name: "Dedup test profile", source: "slr", filters: { hasFullText: true },
    artifact_kinds: ["FULLTEXT_MARKDOWN"], batch_limit: 25, is_active: true,
  }] }));
  await page.route("**/v1/admin/corpus/imports", (route) => route.fulfill({ status: 202, json: { job_id: "job-1", status: "queued" } }));
  const existing = {
    external_id: "incoming", title: "Incoming paper", matched_article_id: "existing-article-123",
    matched_title: "Original paper", matched_source: "upload", matched_status: "failed",
  };
  await page.route("**/v1/admin/jobs/job-1", (route) => route.fulfill({ json: {
    status: "succeeded", result: { listed: 3, imported: 1, skipped_duplicate: 2,
      duplicates: [{ ...existing, reason: "doi" }, { ...existing, reason: "file_sha256" }],
      suspected_duplicates: [{ ...existing, reason: "title", matched_status: "ready" }],
    },
  } }));
  await page.goto("/import");
  await page.getByRole("button", { name: /Dedup test profile/ }).click();
  await page.getByRole("button", { name: "Start import", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Skipped duplicate articles" })).toBeVisible();
  await expect(page.getByText("Same normalized DOI (before download)")).toBeVisible();
  await expect(page.getByText("Identical file (after download)")).toBeVisible();
  await expect(page.getByText("Retry ingestion of the existing article.")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Similar titles to review (imported)" })).toBeVisible();
  await expect(page.getByText("Same normalized title; identity unconfirmed")).toBeVisible();
  await expect(page.getByText("upload · existing-article-123")).toHaveCount(3);
  await page.screenshot({ path: "test-results/slr-dedup.png", fullPage: true });
});
