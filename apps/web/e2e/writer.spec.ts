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
  await page.getByLabel("Manuscript section").selectOption("INTRO");
  await page.getByLabel("Rhetorical intent").selectOption("INTRO_GAP_INDICATE");
  await page.getByLabel("Article genre").selectOption("RESEARCH_ARTICLE");
  await page.getByLabel("Claim type").selectOption("descriptive");
  await page.getByLabel("Evidence level").selectOption("multiple_consistent");
  await page.getByRole("button", { name: "Find patterns" }).click();
  await expect(page.getByText("The role of {topic} in {context} remains underexplored.")).toBeVisible();

  await page.getByRole("textbox", { name: /^\{topic\}/ }).fill("language models");
  await page.getByRole("textbox", { name: /^\{context\}/ }).fill("education");
  await page.getByRole("button", { name: "Build sentence" }).click();
  await expect(page.getByLabel("Draft sentence")).toHaveValue(
    "The role of language models in education remains underexplored.",
  );
  await page.getByRole("button", { name: "Validate sentence" }).click();
  await expect(page.getByText(/Claim check:/)).toBeVisible();
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
