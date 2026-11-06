import { expect, test, type Page } from "@playwright/test";

const baseURL = process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173";

test.use({
  baseURL,
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

async function choose(page: Page, label: string, option: string) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
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
  const results = page.getByRole("radiogroup", { name: "Recommended patterns" });
  await expect(results.getByRole("table")).toBeVisible();
  await expect(page.getByText("Select an evidence level to hide patterns that exceed it.", { exact: false })).toBeVisible();
  await choose(page, "Evidence level", "Single study");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText(/samples hidden because they exceed the selected evidence level/)).toBeVisible();
  await choose(page, "Article genre", "Systematic review");
  await page.getByRole("combobox", { name: "Manuscript section" }).click();
  await expect(page.getByRole("option", { name: "Discussion", exact: true })).toHaveCount(0);
  await page.getByRole("option", { name: "Introduction", exact: true }).click();
  await page.getByRole("combobox", { name: "Rhetorical intent" }).click();
  await expect(page.getByRole("option", { name: "Indicate a research gap", exact: true })).toHaveCount(1);
  await page.keyboard.press("Escape");
  await choose(page, "Article genre", "Research article");
  await page.getByRole("combobox", { name: "Manuscript section" }).click();
  await expect(page.getByRole("option", { name: "Discussion", exact: true })).toHaveCount(1);
  await page.getByRole("option", { name: "Discussion", exact: true }).click();
  await page.getByRole("combobox", { name: "Rhetorical intent" }).click();
  await expect(page.getByRole("option", { name: "Interpret a finding", exact: true })).toHaveCount(1);
  await page.keyboard.press("Escape");
  await choose(page, "Manuscript section", "Introduction");
  await choose(page, "Rhetorical intent", "Indicate a research gap");
  await choose(page, "Claim type", "Descriptive");
  await choose(page, "Evidence level", "Multiple consistent studies");
  await page.getByLabel("Search keywords", { exact: true }).fill("role 45%");
  await page.getByLabel("Supporting context", { exact: true }).fill("The study examined language models in education.");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText("The role of {topic} in {context} remains underexplored.")).toBeVisible();
  await expect(results.getByRole("columnheader", { name: "Evidence alignment" })).toBeVisible();
  await expect(results.getByRole("cell", { name: "—", exact: true }).first()).toBeVisible();
  await expect(page.getByText("Score breakdown:")).toHaveCount(0);

  const topic = page.getByRole("textbox", { name: /^\{topic\}/ });
  const contextSlot = page.getByRole("textbox", { name: /^\{context\}/ });
  await expect(page.getByText("Name the specific topic discussed in your evidence.", { exact: false })).toBeVisible();
  await expect(page.getByText("Example: language models", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByText("This field is required.").first()).toBeVisible();
  await topic.fill("AI");
  await contextSlot.fill("education");
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByText("Enter at least 3 characters.")).toBeVisible();
  await topic.fill("language models");
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByLabel("Draft sentence")).toHaveValue(
    "The role of language models in education remains underexplored.",
  );
  await page.getByLabel("Draft sentence").fill(
    "The really important result was an increase of 45%.",
  );
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText("Claim check", { exact: false })).toBeVisible();
  const fabrication = page.getByRole("alert").filter({ hasText: "V03" });
  await expect(fabrication).toContainText("Block");
  await expect(fabrication).toContainText("A numeric claim is not present in the supplied slots or context");
  const style = page.getByRole("alert").filter({ hasText: "V06" });
  await expect(style).toContainText("Warn");
  await expect(style).toContainText("Potentially informal style phrase: 'really'");
  await expect(page.getByText("V05 is not checked because verified Offline guideline data is unavailable.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy draft" })).toBeDisabled();
  const revised = "The role of language models in education remains poorly understood.";
  await page.getByLabel("Draft sentence").fill(revised);
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText("Claim check", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Copy draft" }).click();
  await expect(page.getByRole("status")).toContainText("Copied as a draft");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(revised);
  await page.getByRole("button", { name: "This pattern is useful" }).click();
  await expect(page.getByRole("button", { name: "Feedback recorded" })).toBeVisible();
  expect(onlineCalls).toEqual([
    "/v1/recommendations", "/v1/recommendations", "/v1/recommendations",
    "/v1/render", "/v1/render", "/v1/render",
    "/v1/validate", "/v1/validate", "/v1/feedback",
  ]);
});
