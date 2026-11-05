import { expect, test, type Page } from "@playwright/test";

const baseURL = process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173";

test.use({
  baseURL,
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

async function select(page: Page, name: string, option: string) {
  await page.getByRole("combobox", { name, exact: true }).click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

test("writer uses PostgreSQL-backed search, render, validate and feedback", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const onlineCalls: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && request.url().includes("/v1/")) {
      onlineCalls.push(new URL(request.url()).pathname);
    }
  });

  await page.goto("/writer");
  await expect(page.getByRole("table", { name: "Recommended patterns" })).toBeVisible();
  await expect(page.getByText(/^Select an evidence level to hide patterns that exceed it/)).toBeVisible();
  await select(page, "Evidence level", "Single study");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByRole("table", { name: "Recommended patterns" })).toBeVisible();
  await select(page, "Article genre", "Systematic review");
  await page.getByRole("combobox", { name: "Manuscript section", exact: true }).click();
  await expect(page.getByRole("option", { name: "Discussion", exact: true })).toHaveCount(0);
  await page.getByRole("option", { name: "Introduction", exact: true }).click();
  await page.getByRole("combobox", { name: "Rhetorical intent", exact: true }).click();
  await expect(page.getByRole("option", { name: "Indicate a research gap", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await select(page, "Article genre", "Research article");
  await select(page, "Manuscript section", "Discussion");
  await page.getByRole("combobox", { name: "Rhetorical intent", exact: true }).click();
  await expect(page.getByRole("option", { name: "Interpret a finding", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await select(page, "Manuscript section", "Methods");
  await select(page, "Rhetorical intent", "Describing previously used methods");
  await select(page, "Claim type", "Descriptive");
  await select(page, "Evidence level", "Multiple consistent studies");
  await page.getByLabel("Search keywords").fill("Many researchers have utilised");
  await page.getByLabel("Supporting context").fill("The study used interviews to measure participant experience.");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText("Many researchers have utilised {x} to measure {details}")).toBeVisible();
  await expect(page.getByRole("table", { name: "Recommended patterns" }).getByText("Evidence alignment", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Recommended patterns" }).getByText("—", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Score breakdown:")).toHaveCount(0);

  const topic = page.getByRole("textbox", { name: /^\{x\}/ });
  const contextSlot = page.getByRole("textbox", { name: /^\{details\}/ });
  await expect(page.getByText(/Replace X with a method, measure, or topic/)).toBeVisible();
  await expect(page.getByText(/Complete with details supported by your study/)).toBeVisible();
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByText("This field is required.").first()).toBeVisible();
  await topic.fill("interviews");
  await contextSlot.fill("participant experience");
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByLabel("Draft sentence")).toHaveValue(
    "Many researchers have utilised interviews to measure participant experience",
  );
  await page.getByLabel("Draft sentence").fill(
    "The really important result was an increase of 45%.",
  );
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText(/Claim check/)).toBeVisible();
  await expect(page.getByText(/A numeric claim is not present in the supplied slots or context/)).toBeVisible();
  await expect(page.getByText(/Potentially informal style phrase: 'really'/)).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "A numeric claim" }).getByText("Block", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Potentially informal" }).getByText("Warn", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy draft" })).toBeDisabled();
  await expect(page.getByText(/V05 is not checked because verified Offline guideline data is unavailable/)).toBeVisible();
  const revised = "The study used interviews to measure participant experience.";
  await page.getByLabel("Draft sentence").fill(revised);
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText(/Claim check/)).toBeVisible();
  await page.getByRole("button", { name: "Copy draft" }).click();
  await expect(page.getByRole("status")).toContainText("Copied as a draft");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(revised);
  await page.getByRole("button", { name: "This pattern is useful" }).click();
  await expect(page.getByRole("button", { name: "Feedback recorded" })).toBeVisible();
  expect(onlineCalls).toEqual([
    "/v1/recommendations", "/v1/recommendations", "/v1/recommendations",
    "/v1/render", "/v1/render",
    "/v1/validate", "/v1/validate", "/v1/feedback",
  ]);
});
