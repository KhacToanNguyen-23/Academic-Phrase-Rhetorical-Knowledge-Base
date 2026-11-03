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
export type ManchesterSearchResult = components["schemas"]["SearchResult"];
export type PatternSummary = components["schemas"]["PatternSummary"];
export type PatternDetail = components["schemas"]["PatternDetail"];
export type TaxonomyTree = components["schemas"]["TaxonomyTree"];

export type TaxonomyFilter = { sectionCode?: string; intentCode?: string };

export interface PhrasebankSource<TGroup, TSearch, TDetail> {
  id: SourceId;
  label: string;
  listGroups(): Promise<TGroup[]>;
  getGroup(id: string): Promise<TDetail>;
  search(query: string, filter?: TaxonomyFilter, groups?: TGroup[]): Promise<TSearch[]>;
  filterBySection(item: TGroup | TSearch, sectionCode: string, taxonomy?: TaxonomyTree): boolean;
  filterByIntent(item: TGroup | TSearch, intentCode: string): boolean;
}

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

function sectionForIntent(taxonomy: TaxonomyTree, intentCode: string): string | undefined {
  for (const section of taxonomy.sections) {
    for (const move of section.moves) {
      for (const step of move.steps) {
        if (step.intents.some((intent) => intent.code === intentCode)) return section.code;
      }
    }
  }
  return undefined;
}

function referenceItemMatchesSection(
  item: ManchesterCategory | ManchesterSearchResult,
  sectionCode: string,
  taxonomy?: TaxonomyTree,
) {
  if (item.section_code === sectionCode) return true;
  if ("slug" in item) {
    return item.intent_codes?.some((code) => taxonomy && sectionForIntent(taxonomy, code) === sectionCode) ?? false;
  }
  return item.intent_code && taxonomy ? sectionForIntent(taxonomy, item.intent_code) === sectionCode : false;
}

export const phrasebankSources = {
  categories: async () => unwrap(await client().GET("/v1/reference-library/categories")),
  category: async (slug: string) => unwrap(await client().GET("/v1/reference-library/categories/{slug}", {
    params: { path: { slug } },
  })),
  search: async (q: string) => unwrap(await client().GET("/v1/reference-library/search", {
    params: { query: { q, limit: 50 } },
  })),
  taxonomy: async () => unwrap(await client().GET("/v1/taxonomy")),
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

const referenceSource: PhrasebankSource<ManchesterCategory, ManchesterSearchResult, ManchesterDetail> = {
  id: "manchester-reference",
  label: "Manchester reference",
  async listGroups() {
    return (await phrasebankSources.categories()).categories;
  },
  getGroup: phrasebankSources.category,
  async search(query, filter = {}) {
    const taxonomy = filter.sectionCode ? await phrasebankSources.taxonomy().catch(() => undefined) : undefined;
    const result = (await phrasebankSources.search(query)).results;
    return result.filter((item) =>
      (!filter.sectionCode || (taxonomy && referenceItemMatchesSection(item, filter.sectionCode, taxonomy)))
      && (!filter.intentCode || item.intent_code === filter.intentCode));
  },
  filterBySection: referenceItemMatchesSection,
  filterByIntent(item, intentCode) {
    return "slug" in item ? (item.intent_codes ?? []).includes(intentCode) : item.intent_code === intentCode;
  },
};

const patternsSource: PhrasebankSource<PatternDetail, PatternDetail, PatternDetail[]> = {
  id: "aprkb-patterns",
  label: "AP-RKB patterns",
  listGroups: phrasebankSources.patterns,
  getGroup: () => phrasebankSources.patterns(),
  async search(query, filter = {}, groups) {
    const patterns = groups ?? await phrasebankSources.patterns();
    const normalized = query.trim().toLocaleLowerCase();
    return patterns.filter((pattern) =>
      (!normalized || `${pattern.canonical_frame ?? ""} ${pattern.intent_code} ${pattern.allowed_sections.join(" ")}`.toLocaleLowerCase().includes(normalized))
      && (!filter.sectionCode || pattern.allowed_sections.includes(filter.sectionCode))
      && (!filter.intentCode || pattern.intent_code === filter.intentCode));
  },
  filterBySection(item, sectionCode) {
    return item.allowed_sections.includes(sectionCode);
  },
  filterByIntent(item, intentCode) {
    return item.intent_code === intentCode;
  },
};

export const PHRASEBANK_SOURCES = {
  "manchester-reference": referenceSource,
  "aprkb-patterns": patternsSource,
} as const;
