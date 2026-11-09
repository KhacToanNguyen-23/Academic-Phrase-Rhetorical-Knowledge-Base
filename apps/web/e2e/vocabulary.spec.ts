import { expect, test, type Page } from "@playwright/test";

async function selectOption(page: Page, label: string, option: string) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("aprkb-staff-session", "test-staff-key"));
  await page.route("**/v1/auth/me", (route) => route.fulfill({
    json: { id: "test-id", name: "Test curator", role: "curator" },
  }));
  await page.route("**/v1/vocabulary/filter-options", (route) => route.fulfill({
    json: { pos: { v: "verb" }, status: { unknown: "Unknown" }, domains: { MED: "Medicine/Health" } },
  }));
});

test("lemma filters work together and reset pagination", async ({ page }) => {
  await page.route("**/v1/vocabulary/families?**", (route) => route.fulfill({ json: { items: [], total: 0 } }));
  await page.route("**/v1/vocabulary/letters**", (route) => {
    const { searchParams } = new URL(route.request().url());
    return route.fulfill({ json: [{ letter: "a", count: searchParams.get("pos") === "v" ? 1 : 51 }] });
  });
  await page.route("**/v1/vocabulary/lemmas?**", (route) => route.fulfill({
    json: {
      total: 51,
      items: [{
        id: "test-lemma", word: "analyse", pos: "v", pos_label: "verb", rank: 1,
        band: 5, status: null, status_label: "", is_core: false, coca_acad: 543,
      }],
    },
  }));

  await page.goto("/vocabulary?offset=50");
  await expect(page.getByRole("link", { name: "Go to previous page" })).toBeEnabled();
  await expect(page.getByText("Core only", { exact: true })).toHaveCount(0);
  await selectOption(page, "Part of speech", "verb");
  await expect(page.getByRole("link", { name: "Go to previous page" })).toBeDisabled();
  await expect(page.getByRole("radio", { name: "A 1 lemmas" })).toBeVisible();
  await selectOption(page, "Status", "Unknown");
  await selectOption(page, "Research field", "Medicine/Health");
  await expect(page.getByText("Showing words tagged for this field or used more often than expected in it.")).toBeVisible();
  await selectOption(page, "Sort order", "Most frequent in academic texts");

  await page.getByRole("spinbutton", { name: "Min band" }).fill("8");
  await page.getByRole("spinbutton", { name: "Max band" }).fill("7");
  await expect(page.getByRole("button", { name: "Apply band" })).toBeDisabled();
  await page.getByRole("spinbutton", { name: "Min band" }).fill("3");
  const filtered = page.waitForRequest((request) => {
    const url = new URL(request.url());
    return url.pathname === "/v1/vocabulary/lemmas" && url.searchParams.get("band_min") === "3";
  });
  await page.getByRole("button", { name: "Apply band" }).click();
  const params = new URL((await filtered).url()).searchParams;
  expect(Object.fromEntries(params)).toMatchObject({
    pos: "v", status: "unknown", domain: "MED", sort: "academic_frequency",
    band_min: "3", band_max: "7", offset: "0",
  });
  await expect(page.getByRole("columnheader", { name: "Academic frequency" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "543" })).toBeVisible();

  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(page.getByRole("combobox", { name: "Part of speech" })).toHaveText("All parts of speech");
  await expect(page.getByRole("spinbutton", { name: "Min band" })).toHaveValue("");
  await page.getByRole("tab", { name: /Word families/ }).click();
  await expect(page.getByRole("combobox", { name: "Part of speech" })).toHaveCount(0);
});

test("word families can page forward and back and restart from a new search", async ({ page }) => {
  await page.route("**/v1/vocabulary/letters**", (route) => route.fulfill({ json: [] }));
  await page.route("**/v1/vocabulary/lemmas?**", (route) => route.fulfill({ json: { items: [], total: 0 } }));
  const families = Array.from({ length: 51 }, (_, index) => ({
    id: `family-${index + 1}`,
    headword: `family ${index + 1}`,
    rank: index + 1,
    family_freq: 100 - index,
    members: [],
  }));
  await page.route("**/v1/vocabulary/families?**", (route) => {
    const { searchParams } = new URL(route.request().url());
    const matches = families.filter((family) => family.headword.startsWith(searchParams.get("q") ?? ""));
    const offset = Number(searchParams.get("offset"));
    const limit = Number(searchParams.get("limit"));
    return route.fulfill({ json: { items: matches.slice(offset, offset + limit), total: matches.length } });
  });

  await page.goto("/vocabulary?view=families");
  const pagination = page.getByRole("navigation", { name: "pagination" });
  const previous = pagination.getByRole("link", { name: "Go to previous page" });
  const next = pagination.getByRole("link", { name: "Go to next page" });
  await expect(pagination).toContainText("1–50 of 51");
  await expect(previous).toBeDisabled();
  await next.click();
  await expect(pagination).toContainText("51–51 of 51");
  await expect(next).toBeDisabled();
  await expect(page.getByText("family 51", { exact: true })).toBeVisible();
  await expect(page.getByText("family 1", { exact: true })).toHaveCount(0);
  await previous.click();
  await expect(pagination).toContainText("1–50 of 51");

  await next.click();
  await expect(pagination).toContainText("51–51 of 51");
  await page.getByRole("searchbox", { name: "Search vocabulary" }).fill("family 51");
  await expect(pagination).toContainText("1–1 of 1");
  await expect(previous).toBeDisabled();
  await expect(next).toBeDisabled();
});
