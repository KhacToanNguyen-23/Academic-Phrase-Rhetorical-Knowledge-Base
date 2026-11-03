import type { components } from "@/shared/api/schema";

export type Batch = components["schemas"]["BatchRead"];
export type ArticleRow = components["schemas"]["ArticleRowRead"];
export type ArticleText = components["schemas"]["ArticleTextRead"];
export type Phrase = components["schemas"]["PhraseRead"];
export type PhrasePage = components["schemas"]["PhrasePage"];
export type PhraseStatus = "pending" | "accepted" | "rejected";

/** Token used in the batch selection for articles that were not imported through a batch. */
export const NO_BATCH = "none";

export const batchToken = (batch: Batch) => batch.batch_id ?? NO_BATCH;

export function toScope(tokens: string[]) {
  return {
    batch_id: tokens.filter((token) => token !== NO_BATCH),
    unbatched: tokens.includes(NO_BATCH),
  };
}

export const PAGE_SIZE = 50;
