import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Full local regression also runs suites which do not set their own browser channel.
export default defineConfig({
  ...base,
  use: {
    ...base.use,
    ...(process.env.WRITER_E2E_BROWSER === "msedge" ? { channel: "msedge" } : {}),
  },
});
