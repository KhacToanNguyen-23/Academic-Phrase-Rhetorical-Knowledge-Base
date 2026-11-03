// Dữ liệu mẫu cho luồng tích hợp Writing ⇄ Wordbank và màn Admin.
// Toàn bộ câu là tự biên soạn; claim_id/evidence là mã giả, không phải citation thật.
import type { ApiClient, Endpoint, RequestLog, Submission } from "./mock-types";

export const CLIENTS: ApiClient[] = [
  { client_id: "cli_writing_prod", name: "Writing Engine", owner: "Writing team", scopes: ["recommend", "render", "validate", "submit"], created_at: "2026-09-02", last_seen: "2026-10-30T09:41:00Z", status: "active" },
  { client_id: "cli_writing_staging", name: "Writing Engine (staging)", owner: "Writing team", scopes: ["recommend", "render", "validate", "submit"], created_at: "2026-09-02", last_seen: "2026-10-30T08:12:00Z", status: "active" },
  { client_id: "cli_slr_planner", name: "SLR Rhetorical Planner", owner: "SLR group", scopes: ["recommend", "taxonomy"], created_at: "2026-10-05", last_seen: "2026-10-29T16:20:00Z", status: "active" },
  { client_id: "cli_eval_script", name: "Ablation evaluation script", owner: "Wordbank team", scopes: ["recommend"], created_at: "2026-10-18", last_seen: "2026-10-21T11:03:00Z", status: "suspended" },
];

export const SUBMISSIONS: Submission[] = [
  { id: "sub_0192", client_id: "cli_writing_prod", received_at: "2026-10-30T09:38:00Z", kind: "frame", text: "While {approach} has proven useful for {task}, its sensitivity to {factor} has received comparatively little attention.", context: { section: "Introduction", intent_id: "INT-GAP", genre: "Original Research", field: "Computer Science" }, claim_id: "A3-C07", license_status: "own_authored", user_opt_in: true, near_duplicate: { pattern_id: "GAP-014", similarity: 0.82 }, status: "pending" },
  { id: "sub_0191", client_id: "cli_writing_prod", received_at: "2026-10-30T09:02:00Z", kind: "sentence", text: "The proposed index was computed separately for each study site to account for regional variation.", context: { section: "Methods", intent_id: "INT-MTH", genre: "Original Research", field: "Environmental Science" }, license_status: "own_authored", user_opt_in: true, status: "pending" },
  { id: "sub_0190", client_id: "cli_writing_staging", received_at: "2026-10-29T17:45:00Z", kind: "frame", text: "Taken together, these results point to {interpretation}, although {caveat}.", context: { section: "Discussion", intent_id: "INT-RES", genre: "Original Research" }, license_status: "own_authored", user_opt_in: true, status: "pending" },
  { id: "sub_0189", client_id: "cli_writing_prod", received_at: "2026-10-29T15:10:00Z", kind: "sentence", text: "Prior reviews have largely overlooked implementation outcomes in low-resource settings.", context: { section: "Introduction", intent_id: "INT-GAP", genre: "SLR", field: "Medicine" }, claim_id: "A5-C02", license_status: "unknown", user_opt_in: false, status: "pending" },
  { id: "sub_0188", client_id: "cli_writing_prod", received_at: "2026-10-28T10:20:00Z", kind: "frame", text: "A further limitation concerns {aspect}, which constrains {scope_of_inference}.", context: { section: "Discussion", intent_id: "INT-LIM", genre: "Original Research" }, license_status: "own_authored", user_opt_in: true, near_duplicate: { pattern_id: "LIM-004", similarity: 0.71 }, status: "approved", decided_by: "editor.minh" },
  { id: "sub_0187", client_id: "cli_writing_staging", received_at: "2026-10-27T14:02:00Z", kind: "sentence", text: "This conclusively proves the superiority of our framework.", context: { section: "Conclusion", intent_id: "INT-RES" }, license_status: "own_authored", user_opt_in: true, status: "rejected", decided_by: "editor.lan" },
];

const ENDPOINTS: Endpoint[] = ["POST /v1/recommendations", "POST /v1/render", "POST /v1/validate", "POST /v1/recommendations", "POST /v1/submissions", "GET /v1/taxonomy"];
const SERVED = [["GAP-014", "GAP-030", "GAP-021"], ["RES-010", "RES-010-v1"], ["BG-003", "AIM-002"], ["LIM-004"], ["GAP-021", "GAP-014"]];

function makeLogs(): RequestLog[] {
  const out: RequestLog[] = [];
  const base = Date.parse("2026-10-30T09:45:00Z");
  for (let i = 0; i < 28; i++) {
    const client = i % 7 === 6 ? CLIENTS[2] : i % 5 === 4 ? CLIENTS[1] : CLIENTS[0];
    let endpoint = ENDPOINTS[i % ENDPOINTS.length];
    if (client.client_id === "cli_slr_planner" && endpoint !== "GET /v1/taxonomy") endpoint = "POST /v1/recommendations";
    const at = new Date(base - i * 1000 * 60 * 23).toISOString();
    const served = SERVED[i % SERVED.length];
    const status = i === 9 ? 429 : i === 15 ? 422 : 200;
    const claim = endpoint === "GET /v1/taxonomy" ? undefined : `A${(i % 6) + 1}-C${String((i * 3) % 20).padStart(2, "0")}`;
    const log: RequestLog = {
      request_id: `req_${(9821 - i).toString(36)}`, at, client_id: client.client_id, endpoint, status,
      latency_ms: 40 + ((i * 37) % 180), claim_id: claim, returned_ids: [], received_ids: [], request: {}, response: {},
    };
    if (status !== 200) {
      log.response = { error: status === 429 ? "rate_limited" : "unknown_intent_id", detail: status === 429 ? "Retry after 30s" : "intent_id INT-XYZ is not in taxonomy v3" };
    } else if (endpoint === "POST /v1/recommendations") {
      log.returned_ids = served;
      log.fallback_tier = i % 3 === 0 ? "field" : "journal_genre";
      log.request = { section: "Introduction", intent_id: "INT-GAP", genre: "Original Research", journal_id: "J-001", claim_id: claim, evidence_level: "moderate", top_k: 3 };
      log.response = { request_id: log.request_id, fallback_tier: log.fallback_tier, candidates: served.map((id, r) => ({ candidate_id: id, rank: r + 1, score: +(0.82 - r * 0.04).toFixed(2) })) };
    } else if (endpoint === "POST /v1/render") {
      log.returned_ids = [served[0]];
      log.request = { pattern_id: served[0], slots: { research_focus: "…", specific_condition: "…" }, claim_id: claim };
      log.response = { text: "Although … has been examined, its behavior under … remains insufficiently characterized.", unfilled_slots: [] };
    } else if (endpoint === "POST /v1/validate") {
      log.verdict = i % 4 === 2 ? "block" : i % 4 === 1 ? "warn" : "pass";
      log.request = { text: "These results indicate that …", evidence_level: "moderate", evidence_ids: ["A3-E12"], claim_id: claim };
      log.response = { verdict: log.verdict, violations: log.verdict === "pass" ? [] : [{ code: "V02", severity: log.verdict }] };
    } else if (endpoint === "POST /v1/submissions") {
      const sub = SUBMISSIONS[Math.floor(i / 6) % SUBMISSIONS.length];
      log.received_ids = [sub.id];
      log.request = { kind: sub.kind, text: sub.text, context: sub.context, license_status: sub.license_status, user_opt_in: sub.user_opt_in };
      log.response = { submission_id: sub.id, status: "pending_review" };
    } else {
      log.request = { version: "latest" };
      log.response = { taxonomy_version: "v3", intents: 6 };
    }
    out.push(log);
  }
  return out;
}

export const LOGS: RequestLog[] = makeLogs();
