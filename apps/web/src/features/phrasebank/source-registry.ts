import { createBackendClient } from "@/shared/api/contract-client";
import type { components } from "@/shared/api/schema";
import { unwrap } from "@/features/slr-import/api/client";

export const SOURCE_REGISTRY = [
  { id: "manchester-reference", label: "Manchester reference", family: "external" },
  { id: "aprkb-patterns", label: "AP-RKB patterns", family: "internal" },
] as const;

export type SourceId = (typeof SOURCE_REGISTRY)[number]["id"];
export type ManchesterCategory = components["schemas"]["ReferenceCategoryRead"];
export type ManchesterDetail = components["schemas"]["CategoryDetailResponse"];
export type ManchesterSearch = components["schemas"]["SearchResponse"];
export type PatternSummary = components["schemas"]["PatternSummary"];
export type PatternDetail = components["schemas"]["PatternDetail"];

function client() {
  const api = createBackendClient(import.meta.env.VITE_API_BASE_URL ?? "");
  api.use({
    onRequest({ request }) {
      const key = sessionStorage.getItem("aprkb-api-key");
      if (key) request.headers.set("X-API-Key", key);
      return request;
    },
  });
  return api;
}

export const phrasebankSources = {
  categories: async () => unwrap(await client().GET("/v1/reference-library/categories")),
  category: async (slug: string) => unwrap(await client().GET("/v1/reference-library/categories/{slug}", {
    params: { path: { slug } },
  })),
  search: async (q: string) => unwrap(await client().GET("/v1/reference-library/search", {
    params: { query: { q, limit: 50 } },
  })),
  patterns: async (): Promise<PatternDetail[]> => {
    const api = client();
    const summaries = unwrap(await api.GET("/v1/patterns", {
      params: { query: { status: "approved", limit: 200 } },
    }));
    return Promise.all(summaries.map(async (item) => unwrap(await api.GET("/v1/patterns/{pattern_id}", {
      params: { path: { pattern_id: item.id } },
    }))));
  },
};
