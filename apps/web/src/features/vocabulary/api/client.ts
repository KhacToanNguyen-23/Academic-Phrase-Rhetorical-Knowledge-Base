import { useQuery } from "@tanstack/react-query";

import { createBackendClient } from "@/shared/api/contract-client";
import type { components, paths } from "@/shared/api/schema";
import { unwrap } from "@/features/slr-import/api/client";

export type LemmaPage = components["schemas"]["LemmaPage"];
export type LemmaDetail = components["schemas"]["LemmaDetail"];
export type LetterCount = components["schemas"]["LetterCount"];
export type FamilyPage = components["schemas"]["FamilyPage"];
type LemmaQuery = NonNullable<paths["/v1/vocabulary/lemmas"]["get"]["parameters"]["query"]>;
type LetterQuery = NonNullable<paths["/v1/vocabulary/letters"]["get"]["parameters"]["query"]>;

export function vocabularyClient() {
  const client = createBackendClient(import.meta.env.VITE_API_BASE_URL ?? "");
  client.use({
    onRequest({ request }) {
      const key =
        sessionStorage.getItem("aprkb-staff-session") ?? sessionStorage.getItem("aprkb-api-key");
      if (key) request.headers.set("X-API-Key", key);
      return request;
    },
  });
  return client;
}

export function useLemmas(params: LemmaQuery) {
  return useQuery({
    queryKey: ["vocabulary-lemmas", params],
    queryFn: async (): Promise<LemmaPage> =>
      unwrap(await vocabularyClient().GET("/v1/vocabulary/lemmas", { params: { query: params } })) as LemmaPage,
  });
}

export function useLetters(params: LetterQuery = {}) {
  return useQuery({
    queryKey: ["vocabulary-letters", params],
    queryFn: async (): Promise<LetterCount[]> =>
      unwrap(await vocabularyClient().GET("/v1/vocabulary/letters", { params: { query: params } })) ?? [],
  });
}

export function useVocabularyFilterOptions() {
  return useQuery({
    queryKey: ["vocabulary-filter-options"],
    queryFn: async () => unwrap(await vocabularyClient().GET("/v1/vocabulary/filter-options")),
  });
}

export function useFamilies(params: { q?: string; limit: number; offset: number }) {
  return useQuery({
    queryKey: ["vocabulary-families", params],
    queryFn: async (): Promise<FamilyPage> =>
      unwrap(
        await vocabularyClient().GET("/v1/vocabulary/families", {
          params: { query: params },
        }),
      ) as FamilyPage,
  });
}

export function useLemma(id: string) {
  return useQuery({
    queryKey: ["vocabulary-lemma", id],
    enabled: Boolean(id),
    queryFn: async (): Promise<LemmaDetail> =>
      unwrap(await vocabularyClient().GET("/v1/vocabulary/lemmas/{lemma_id}", { params: { path: { lemma_id: id } } })) as LemmaDetail,
  });
}
