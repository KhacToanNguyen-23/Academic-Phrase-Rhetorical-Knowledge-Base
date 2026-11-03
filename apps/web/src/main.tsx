import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@/app/globals.css";
import "@/app/styles.css";
import { App } from "@/app/App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
