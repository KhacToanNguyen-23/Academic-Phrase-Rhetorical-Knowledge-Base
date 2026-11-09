import { expect, test, type Page } from "@playwright/test";

const id = "30000000-0000-4000-8000-000000000001";
const alertId = "30000000-0000-4000-8000-000000000002";
const failedAt = "2026-11-05T06:00:00Z";
async function mockApi(page: Page, role = "curator", conflict = false) {
  const posts: { path: string; body: Record<string, unknown> }[] = [];
  const gets: string[] = [];
  let job = { id, type: "import_articles", status: "failed", attempts: 4, max_attempts: 4,
    next_attempt_at: null, error_code: "transport_unavailable", error: "Processing failed (ConnectError)",
    result: null, created_at: failedAt, updated_at: failedAt, locked_at: null,
    manual_retries: 0, manual_retry_limit: 3, progress_stage: "listing_articles",
    progress_completed: null, progress_total: null };
  let acknowledged = false;
  await page.addInitScript(() => sessionStorage.setItem("aprkb-web-session", "jobs-ui-test"));
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const post = route.request().method() === "POST";
    if (post) posts.push({ path, body: route.request().postDataJSON() });
    else gets.push(path);
    let data: unknown;
    if (path === "/v1/auth/session/me") data = { id, name: "Operator", role };
    else if (path === "/v1/admin/jobs") data = !url.searchParams.get("status") || url.searchParams.get("status") === job.status ? [job] : [];
    else if (path === `/v1/admin/jobs/${id}`) data = job;
    else if (path.endsWith("/attempts")) data = [{ id: alertId, attempt_no: 4, started_at: failedAt, ended_at: failedAt, outcome: "failed", stage: "listing_articles", completed: null, total: null, error_code: "transport_unavailable", error: "Processing failed (ConnectError)", next_attempt_at: null }];
    else if (path === "/v1/admin/job-alerts") data = [{ id: alertId, job_id: id, failure_count: 4, last_error_code: "transport_unavailable", last_failed_at: failedAt, active: true, acknowledged_at: acknowledged ? failedAt : null, resolved_at: null }];
    else if (path.endsWith("/acknowledge")) { acknowledged = true; data = { id: alertId }; }
    else if (path.endsWith("/retry")) {
      if (conflict) return route.fulfill({ status: 409, json: { error: { message: "Job changed; refresh before retrying" } } });
      job = { ...job, status: "queued", max_attempts: 5, manual_retries: 1, progress_stage: "waiting_for_retry" };
      data = job;
    }
    else return route.fulfill({ status: 404, json: { error: { message: `Unexpected ${path}` } } });
    return route.fulfill({ json: data });
  });
  return { posts, gets };
}

test("operator acknowledges alert and queues exactly one reasoned retry", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const { posts } = await mockApi(page);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/jobs?job=${id}`);
  await expect(page.getByRole("heading", { name: "Jobs", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Attempt history" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry once" })).toBeDisabled();
  await page.getByRole("button", { name: "Acknowledge", exact: true }).click();
  await expect(page.getByText("Acknowledged", { exact: true })).toBeVisible();
  await page.getByLabel("Reason for manual retry").fill("Network configuration repaired");
  await expect(page.getByRole("button", { name: "Retry once" })).toBeEnabled();
  await page.getByRole("button", { name: "Retry once" }).click();
  await expect(page.getByText("One additional attempt queued. Existing history is preserved.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry once" })).toBeDisabled();
  expect(posts.filter((post) => post.path.endsWith("/retry"))).toEqual([{ path: `/v1/admin/jobs/${id}/retry`, body: { expected_attempts: 4, rationale: "Network configuration repaired" } }]);
  await page.screenshot({ path: "test-results/jobs-desktop-light.png", fullPage: true });
  await page.evaluate(() => document.documentElement.classList.add("dark"));
  await page.setViewportSize({ width: 1024, height: 900 });
  await page.screenshot({ path: "test-results/jobs-1024-dark.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test("conflicting retry stays visible and is never automatically retried", async ({ page }) => {
  const { posts } = await mockApi(page, "curator", true);
  await page.goto(`/jobs?job=${id}`);
  await page.getByLabel("Reason for manual retry").fill("Network configuration repaired");
  await page.getByRole("button", { name: "Retry once" }).click();
  await expect(page.getByRole("alert")).toContainText("Job changed");
  expect(posts.filter((post) => post.path.endsWith("/retry"))).toHaveLength(1);
});

test("reviewer cannot load operational job data", async ({ page }) => {
  const { gets } = await mockApi(page, "reviewer");
  await page.goto("/jobs");
  await expect(page).toHaveURL(/\/signin/);
  expect(gets.some((path) => path.startsWith("/v1/admin/"))).toBe(false);
});

test("guest must sign in before viewing jobs", async ({ page }) => {
  await page.goto("/jobs");
  await expect(page).toHaveURL(/\/signin/);
});
