import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

test.skip(process.env.PDF_IMPORT_LIVE !== "1", "Requires the isolated PDF API/worker fixture");
test.use({ browserName: "chromium", ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" as const } : {}) });

// Self-authored one-page PDF; alternate properties change bytes, not scientific text.
function pdf(text: string, title: string) {
  const escape = (value: string) => value.replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)");
  const stream = `BT /F1 12 Tf 50 740 Td ${text.split("\n").map((line) => `(${escape(line)}) Tj 0 -18 Td`).join(" ")} ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`,
    `<< /Title (${escape(title)}) /Author (Alice Example) /CreationDate (D:20200101000000Z) >>`,
  ];
  let document = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(document)); document += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = Buffer.byteLength(document);
  document += `xref\n0 7\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size 7 /Root 1 0 R /Info 6 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(document);
}

async function staff(page: Page, request: APIRequestContext) {
  const response = await request.post("/v1/auth/demo-session");
  expect(response.ok()).toBeTruthy();
  const session = await response.json();
  await page.addInitScript((key: string) => sessionStorage.setItem("aprkb-staff-session", key), session.api_key);
  await page.goto("/import");
  await expect(page.getByRole("heading", { name: "Corpus import", exact: true })).toBeVisible();
  return session.api_key as string;
}

test("PDF preview, reviewed metadata, real worker and text-duplicate detection", async ({ page, request }, testInfo) => {
  const key = await staff(page, request);
  const suffix = `${Date.now()}-${testInfo.retry}`;
  const content = `Introduction\nDOI: 10.1234/pdf-${suffix}\nThis self-authored paper examines academic phrase retrieval.\nThe results suggest an effect under the observed conditions.\nTrial identifier ${suffix}.`;
  await page.getByLabel("PDF file", { exact: true }).setInputFiles({ name: "paper.pdf", mimeType: "application/pdf", buffer: pdf(content, "Unreviewed PDF title") });
  const previewResponse = page.waitForResponse((response) => response.url().includes("/corpus/pdf/preview"));
  await page.getByLabel("PDF license", { exact: true }).selectOption("CC-BY");
  await page.getByRole("button", { name: "Preview PDF and check duplicates" }).click();
  expect((await previewResponse).status()).toBe(200);
  await expect(page.getByLabel("PDF title", { exact: true })).toHaveValue("Unreviewed PDF title");
  await expect(page.getByLabel("Publication year (optional)")).toHaveValue("");
  await expect(page.getByLabel("Paper DOI (optional)")).toHaveValue("");
  await page.getByLabel("PDF title", { exact: true }).fill(`Reviewed PDF ${suffix}`);
  await page.getByLabel("Paper DOI (optional)").fill(`https://doi.org/10.1234/pdf-${suffix}`);
  await page.getByLabel("Authors (separate with semicolons)").fill("Alice Example; Bob Example");
  await page.getByLabel("Publication year (optional)").fill("2026");
  await expect(page.getByRole("button", { name: "Import reviewed PDF" })).toBeDisabled();
  await page.getByRole("checkbox", { name: /I reviewed these metadata/ }).check();
  const uploadResponse = page.waitForResponse((response) => response.url().endsWith("/v1/admin/corpus/articles") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Import reviewed PDF" }).click();
  const uploaded = await uploadResponse;
  expect(uploaded.status()).toBe(202);
  const result = await uploaded.json();
  await expect(page.getByText("Ready for extraction.", { exact: false })).toBeVisible({ timeout: 20_000 });
  const meta = await request.get(`/v1/admin/corpus/articles/${result.article_id}/metadata`, { headers: { "X-API-Key": key } });
  expect(await meta.json()).toMatchObject({ title: `Reviewed PDF ${suffix}`, authors: ["Alice Example", "Bob Example"], publication_year: 2026, ingest_status: "ready", page_count: 1 });
  const text = await request.get(`/v1/admin/corpus/articles/${result.article_id}/text`, { headers: { "X-API-Key": key } });
  expect((await text.json()).sections[0]).toMatchObject({ page_number: 1, section_code: "INTRO" });
  await page.screenshot({ path: testInfo.outputPath("pdf-import-ready.png"), fullPage: true });
  await page.getByLabel("PDF file", { exact: true }).setInputFiles({ name: "different-name.pdf", mimeType: "application/pdf", buffer: pdf(content, "Changed PDF properties") });
  await page.getByRole("button", { name: "Preview PDF and check duplicates" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Duplicate (pdf_text_sha256)" })).toContainText(result.article_id);
  await expect(page.getByRole("button", { name: "Import reviewed PDF" })).toHaveCount(0);
});

test("invalid or textless PDF is actionable and never offers import", async ({ page, request }) => {
  await staff(page, request);
  await page.getByLabel("PDF license", { exact: true }).selectOption("CC-BY");
  for (const [buffer, message] of [[Buffer.from("not a PDF"), "not a PDF"], [pdf("", "Textless file"), "OCR first"]] as const) {
    await page.getByLabel("PDF file", { exact: true }).setInputFiles({ name: "bad.pdf", mimeType: "application/pdf", buffer });
    await page.getByRole("button", { name: "Preview PDF and check duplicates" }).click();
    await expect(page.getByRole("alert")).toContainText(message);
    await expect(page.getByRole("button", { name: "Import reviewed PDF" })).toHaveCount(0);
  }
});
