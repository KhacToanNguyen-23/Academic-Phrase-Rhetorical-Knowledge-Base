import { expect, test } from "@playwright/test";

const baseURL = process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173";

test.use({ baseURL, browserName: "chromium" });

test("phrasebank keeps its source notice and explains a disabled Manchester source", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("aprkb-staff-session", "test-staff-key"));
  await page.route("**/v1/auth/me", async (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ id: "test-id", name: "Test curator", role: "curator" }),
  }));
  await page.route("**/v1/reference-library/**", async (route) => route.fulfill({
    status: 404,
    contentType: "application/json",
    body: JSON.stringify({ error: { code: "NOT_FOUND", message: "Reference library is disabled", details: null }, request_id: "test" }),
  }));
  await page.route("**/v1/patterns**", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));

  await page.goto("/phrasebank");
  await expect(page.getByText("Source: University of Manchester Academic Phrasebank.", { exact: false })).toBeVisible();
  await expect(page.getByText(/Manchester reference is disabled/).first()).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Source filter" })).toHaveValue("all");
});
