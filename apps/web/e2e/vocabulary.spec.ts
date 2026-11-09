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
  await expect(page.getByText("Build a research paper sample to enable this filter.")).toBeVisible();
  await expect(page.getByText("Core only", { exact: true })).toHaveCount(0);
  await selectOption(page, "Part of speech", "verb");
  await expect(page.getByRole("link", { name: "Go to previous page" })).toBeDisabled();
  await expect(page.getByRole("radio", { name: "A 1 lemmas" })).toBeVisible();
  await selectOption(page, "Status", "Unknown");
  await selectOption(page, "Discipline", "Medicine/Health");
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

test("research fields scope their subfields and show sampled-paper evidence", async ({ page }) => {
  await page.route("**/v1/vocabulary/filter-options", (route) => route.fulfill({
    json: {
      pos: { v: "verb" }, status: { unknown: "Unknown" }, domains: { MED: "Medicine/Health" },
      research_groups: [
        { key: "field:27", field_id: "27", field_name: "Medicine", subfield_id: null, subfield_name: null, paper_count: 5 },
        { key: "subfield:2730", field_id: "27", field_name: "Medicine", subfield_id: "2730", subfield_name: "Oncology", paper_count: 3 },
        { key: "field:17", field_id: "17", field_name: "Computer Science", subfield_id: null, subfield_name: null, paper_count: 5 },
      ],
    },
  }));
  await page.route("**/v1/vocabulary/families?**", (route) => route.fulfill({ json: { items: [], total: 0 } }));
  await page.route("**/v1/vocabulary/letters**", (route) => {
    const { searchParams } = new URL(route.request().url());
    const count = searchParams.get("research_group") === "subfield:2730" ? 1 : 51;
    return route.fulfill({ json: [{ letter: "a", count }] });
  });
  await page.route("**/v1/vocabulary/lemmas?**", (route) => {
    const { searchParams } = new URL(route.request().url());
    const researchGroup = searchParams.get("research_group");
    return route.fulfill({
      json: {
        total: researchGroup ? 1 : 51,
        items: [{
          id: "test-lemma", word: "analyse", pos: "v", pos_label: "verb", rank: 1,
          band: 5, status: null, status_label: "", is_core: false, coca_acad: 543,
          research_evidence: researchGroup
            ? { paper_count: 2, sample_count: researchGroup === "subfield:2730" ? 3 : 5 }
            : null,
        }],
      },
    });
  });

  await page.goto("/vocabulary?pos=v&offset=50");
  await expect(page.getByRole("link", { name: "Go to previous page" })).toBeEnabled();
  await expect(page.getByRole("combobox", { name: "Subfield", exact: true })).toHaveCount(0);
  await selectOption(page, "Research field", "Medicine");
  await expect(page.getByRole("link", { name: "Go to previous page" })).toBeDisabled();
  await expect(page.getByRole("cell", { name: "2 of 5 sampled papers" })).toBeVisible();
  await selectOption(page, "Subfield", "Oncology");
  await expect(page.getByRole("radio", { name: "A 1 lemmas" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "2 of 3 sampled papers" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Part of speech" })).toHaveText("verb");

  await selectOption(page, "Research field", "Computer Science");
  await expect(page.getByRole("combobox", { name: "Subfield", exact: true })).toHaveCount(0);
  await expect(page).not.toHaveURL(/researchSubfield=/);
  await expect(page.getByRole("cell", { name: "2 of 5 sampled papers" })).toBeVisible();

  await page.goto("/vocabulary?pos=v&offset=50&researchField=field%3A17&researchSubfield=subfield%3A2730");
  await expect(page).not.toHaveURL(/researchSubfield=/);
  await expect(page.getByRole("combobox", { name: "Research field" })).toHaveText("Computer Science");
  await expect(page.getByRole("link", { name: "Go to previous page" })).toBeDisabled();

  await page.goto("/vocabulary?pos=v&offset=50&researchField=field%3A999");
  await expect(page).not.toHaveURL(/researchField=/);
  await expect(page.getByRole("combobox", { name: "Research field" })).toHaveText("All research fields");
  await expect(page.getByRole("link", { name: "Go to previous page" })).toBeDisabled();
});
