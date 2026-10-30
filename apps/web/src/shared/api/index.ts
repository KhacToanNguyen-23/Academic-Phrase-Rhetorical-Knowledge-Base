// Lớp gọi API dùng chung. Hiện chạy trên mock (backend chưa có endpoint);
// khi có openapi.json: `pnpm gen:api` rồi thay thân hàm bằng openapi-fetch tới /v1/... — chữ ký giữ nguyên.
import { FIELDS, INTENTS, JOURNALS, PATTERNS } from "./mock-data";
import { recommend, validate } from "./mock-engine";
import { CLIENTS, LOGS, SUBMISSIONS } from "./mock-integration";
import type { PatternStatus, RecommendationRequest, Section, SubmissionStatus, ValidationRequest } from "./types";
import { renderFrame } from "@/shared/lib";

export * from "./types";

const delay = <T,>(value: T, ms = 180) => new Promise<T>((r) => setTimeout(() => r(value), ms));

export interface PatternQuery {
  q?: string;
  section?: Section;
  intent_id?: string;
  status?: PatternStatus;
}

export const api = {
  intents: () => delay(INTENTS),
  fields: () => delay(FIELDS),
  journals: () => delay(JOURNALS.map(({ journal_id, title, issn_l }) => ({ journal_id, title, issn_l }))),

  // ── Bank (Library) ──
  // GET /v1/patterns
  patterns: (f: PatternQuery) => {
    const q = f.q?.trim().toLowerCase();
    return delay(PATTERNS.filter((p) =>
      (!f.section || p.section_scope.includes(f.section)) &&
      (!f.intent_id || p.intent_id === f.intent_id) &&
      (!f.status || p.status === f.status) &&
      (!q || p.canonical_frame.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)),
    ));
  },
  // GET /v1/patterns/{id}
  pattern: (id: string) => delay(PATTERNS.find((p) => p.id === id) ?? null),
  // GET /v1/journals/{id}
  journal: (id: string) => delay(JOURNALS.find((j) => j.journal_id === id) ?? null),

  // ── API mà Writing Engine gọi (Playground mô phỏng) ──
  // POST /v1/recommendations
  recommend: (req: RecommendationRequest) => delay(recommend(req), 300),
  // POST /v1/render — slot thiếu giữ placeholder (BR-02)
  render: (req: { pattern_id: string; frame: string; slots: Record<string, string> }) => {
    const text = renderFrame(req.frame, req.slots);
    return delay({ text, unfilled_slots: [...text.matchAll(/\{([a-z_]+)\}/g)].map((m) => m[1]) }, 150);
  },
  // POST /v1/validate
  validate: (req: ValidationRequest) => delay(validate(req), 250),

  // ── Dữ liệu vào (Inbox) ──
  // GET /v1/submissions
  submissions: (status?: SubmissionStatus) => delay(SUBMISSIONS.filter((s) => !status || s.status === status).map((s) => ({ ...s }))),
  // POST /v1/submissions/{id}/decision — audit ghi ở backend (NFR-03)
  decide: (id: string, status: Exclude<SubmissionStatus, "pending">) => {
    const s = SUBMISSIONS.find((x) => x.id === id);
    if (s) Object.assign(s, { status, decided_by: "you" });
    return delay(s ?? null, 200);
  },

  // ── Admin ──
  clients: () => delay(CLIENTS),
  logs: () => delay(LOGS),
};
