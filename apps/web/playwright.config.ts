import { defineConfig } from "@playwright/test";

// API/Vite must already be running against a disposable aprkb_test database; see
// e2e/README or apps/web/README.md. CI treats this suite as Stage A (non-blocking
// observability) until a stability window justifies promoting it to a required check.
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]] : "list",
  use: {
    baseURL: process.env.WRITER_E2E_BASE_URL ?? "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
