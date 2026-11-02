import { expect, test } from "@playwright/test";

const baseURL = process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173";

test.use({
  baseURL,
  browserName: "chromium",
  ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}),
});

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
  await expect(page.getByText("Select an evidence level to hide patterns that exceed it.")).toBeVisible();
  await page.getByLabel("Evidence level").selectOption("single_study");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText(/samples hidden because they exceed the selected evidence level/)).toBeVisible();
  const genre = page.getByLabel("Article genre");
  const section = page.getByLabel("Manuscript section");
  const intent = page.getByLabel("Rhetorical intent");
  await genre.selectOption("SYSTEMATIC_REVIEW");
  await expect(section.locator('option[value="DISCUSSION"]')).toHaveCount(0);
  await section.selectOption("INTRO");
  await expect(intent.locator('option[value="INTRO_GAP_INDICATE"]')).toHaveCount(1);
  await genre.selectOption("RESEARCH_ARTICLE");
  await expect(section.locator('option[value="DISCUSSION"]')).toHaveCount(1);
  await section.selectOption("DISCUSSION");
  await expect(intent.locator('option[value="DISCUSSION_FINDING"]')).toHaveCount(1);
  await section.selectOption("INTRO");
  await intent.selectOption("INTRO_GAP_INDICATE");
  await page.getByLabel("Claim type").selectOption("descriptive");
  await page.getByLabel("Evidence level").selectOption("multiple_consistent");
  await page.getByLabel("Search keywords (optional)").fill("45%");
  await page.getByLabel("Supporting context (optional)").fill("The study examined language models in education.");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText("The role of {topic} in {context} remains underexplored.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Recommended patterns" }).getByText("Evidence alignment", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Recommended patterns" }).getByText("—", { exact: true })).toBeVisible();
  await expect(page.getByText("Score breakdown:")).toHaveCount(0);

  const topic = page.getByRole("textbox", { name: /^\{topic\}/ });
  const contextSlot = page.getByRole("textbox", { name: /^\{context\}/ });
  await expect(page.getByText("Name the specific topic discussed in your evidence.")).toBeVisible();
  await expect(page.getByText("Example: language models")).toBeVisible();
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
  await expect(page.getByText(/Claim check:/)).toBeVisible();
  await expect(page.getByText(/Blocked: A numeric claim is not present in the supplied slots or context/)).toBeVisible();
  await expect(page.getByText(/Warning: Potentially informal style phrase: 'really'/)).toBeVisible();
  await expect(page.getByText("V05 not checked: verified Offline guideline data is unavailable.")).toBeVisible();
  const revised = "The role of language models in education remains poorly understood.";
  await page.getByLabel("Draft sentence").fill(revised);
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText(/Claim check:/)).toBeVisible();
  await page.getByRole("button", { name: "Copy draft" }).click();
  await expect(page.getByRole("status")).toContainText("Copied as a draft");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(revised);
  await page.getByRole("button", { name: "This pattern is useful" }).click();
  await expect(page.getByRole("button", { name: "Feedback recorded" })).toBeVisible();
  expect(onlineCalls).toEqual([
    "/v1/recommendations", "/v1/render", "/v1/validate", "/v1/validate", "/v1/feedback",
  ]);
});
