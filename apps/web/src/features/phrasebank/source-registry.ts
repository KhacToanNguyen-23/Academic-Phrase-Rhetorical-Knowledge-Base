import { withSessionApiKey } from "@/features/auth/session";
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
  search(query: string, filter?: TaxonomyFilter): Promise<TSearch[]>;
  filterBySection(item: TGroup | TSearch, sectionCode: string, taxonomy?: TaxonomyTree): boolean;
  filterByIntent(item: TGroup | TSearch, intentCode: string): boolean;
}

function client() {
  return withSessionApiKey(createBackendClient(import.meta.env.VITE_API_BASE_URL ?? ""));
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
  search: async (q: string, filter: TaxonomyFilter = {}) => unwrap(await client().GET("/v1/reference-library/search", {
    params: { query: { q, section: filter.sectionCode, intent: filter.intentCode, phrase_only: true, limit: 50 } },
  })),
  taxonomy: async () => unwrap(await client().GET("/v1/taxonomy")),
  patterns: async (q?: string, filter: TaxonomyFilter = {}): Promise<PatternDetail[]> => {
    return unwrap(await client().GET("/v1/patterns", {
      params: { query: { status: "approved", q: q || undefined, section: filter.sectionCode, intent: filter.intentCode, limit: 200 } },
    }));
  },
  pattern: async (id: string): Promise<PatternDetail> => unwrap(await client().GET("/v1/patterns/{pattern_id}", {
    params: { path: { pattern_id: id } },
  })),
};

const referenceSource: PhrasebankSource<ManchesterCategory, ManchesterSearchResult, ManchesterDetail> = {
  id: "manchester-reference",
  label: "Manchester reference",
  async listGroups() {
    return (await phrasebankSources.categories()).categories;
  },
  getGroup: phrasebankSources.category,
  async search(query, filter = {}) {
    return (await phrasebankSources.search(query, filter)).results;
  },
  filterBySection: referenceItemMatchesSection,
  filterByIntent(item, intentCode) {
    return "slug" in item ? (item.intent_codes ?? []).includes(intentCode) : item.intent_code === intentCode;
  },
};

const patternsSource: PhrasebankSource<PatternDetail, PatternDetail, PatternDetail[]> = {
  id: "aprkb-patterns",
  label: "AP-RKB patterns",
  listGroups: () => phrasebankSources.patterns(),
  getGroup: () => phrasebankSources.patterns(),
  async search(query, filter = {}) {
    return phrasebankSources.patterns(query, filter);
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
