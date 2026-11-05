import { useQuery } from "@tanstack/react-query";

import { withSessionApiKey } from "@/features/auth/session";
import { createBackendClient } from "@/shared/api/contract-client";
import type { components } from "@/shared/api/schema";
import { unwrap } from "@/features/slr-import/api/client";

export type LemmaPage = components["schemas"]["LemmaPage"];
export type LemmaDetail = components["schemas"]["LemmaDetail"];
export type LetterCount = components["schemas"]["LetterCount"];
export type FamilyPage = components["schemas"]["FamilyPage"];

export function vocabularyClient() {
  return withSessionApiKey(createBackendClient(import.meta.env.VITE_API_BASE_URL ?? ""));
}

export function useLemmas(params: {
  q?: string;
  letter?: string;
  core_only?: boolean;
  sort?: "alpha" | "rank";
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: ["vocabulary-lemmas", params],
    queryFn: async (): Promise<LemmaPage> =>
      unwrap(await vocabularyClient().GET("/v1/vocabulary/lemmas", { params: { query: params } })) as LemmaPage,
  });
}

export function useLetters(coreOnly: boolean) {
  return useQuery({
    queryKey: ["vocabulary-letters", coreOnly],
    queryFn: async (): Promise<LetterCount[]> =>
      (unwrap(await vocabularyClient().GET("/v1/vocabulary/letters", { params: { query: { core_only: coreOnly } } })) ?? []) as LetterCount[],
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
