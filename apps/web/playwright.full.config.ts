import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Run the same live regression locally and in CI, including shared browser settings.
export default defineConfig({
  ...base,
  failOnFlakyTests: !!process.env.CI,
  use: {
    ...base.use,
    ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" } : {}),
  },
});
