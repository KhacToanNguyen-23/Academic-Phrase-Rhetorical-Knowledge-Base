// Lớp gọi API dùng chung. Hiện chạy trên mock (backend chưa có endpoint);
// khi có openapi.json: `pnpm gen:api` rồi thay thân hàm bằng openapi-fetch tới /v1/... — chữ ký giữ nguyên.
import { FIELDS, INTENTS, JOURNALS, PATTERNS } from "./mock-data";
import { recommend, validate } from "./mock-engine";
import type { RecommendationRequest, ValidationRequest } from "./types";

export * from "./types";

const delay = <T,>(value: T, ms = 180) => new Promise<T>((r) => setTimeout(() => r(value), ms));

export const api = {
  intents: () => delay(INTENTS),
  fields: () => delay(FIELDS),
  journals: () => delay(JOURNALS.map(({ journal_id, title, issn_l }) => ({ journal_id, title, issn_l }))),
  // POST /v1/recommendations
  recommend: (req: RecommendationRequest) => delay(recommend(req), 300),
  // GET /v1/patterns/{id}
  pattern: (id: string) => delay(PATTERNS.find((p) => p.id === id) ?? null),
  // GET /v1/journals/{id}
  journal: (id: string) => delay(JOURNALS.find((j) => j.journal_id === id) ?? null),
  // POST /v1/validate
  validate: (req: ValidationRequest) => delay(validate(req), 250),
};
