// Mô phỏng recommendation (PRD-07) và validator (PRD-08) phía client cho tới khi backend có endpoint.
// Logic thật nằm ở backend; file này chỉ đủ để UI thể hiện đúng hợp đồng (hard gates, breakdown, fallback_tier, V01–V08).
import { INTENTS, JOURNALS, PATTERNS } from "./mock-data";
import type {
  Candidate,
  EpistemicStrength,
  RecommendationRequest,
  RecommendationResponse,
  ValidationRequest,
  ValidationResult,
  Violation,
} from "./mock-types";

const WEIGHTS = { intent_section: 0.25, disciplinary_fit: 0.2, journal_genre: 0.2, evidence_alignment: 0.15, linguistic_quality: 0.1, provenance_confidence: 0.1 };
const STRENGTH_RANK: Record<EpistemicStrength, number> = { low: 0, moderate: 1, high: 2 };

export function recommend(req: RecommendationRequest): RecommendationResponse {
  const q = req.query?.trim().toLowerCase();
  const scoped = PATTERNS.filter(
    (p) =>
      (!req.intent_id || p.intent_id === req.intent_id) &&
      (!req.section || p.section_scope.includes(req.section)) &&
      (!req.claim_type || p.claim_type === req.claim_type) &&
      (!q || p.canonical_frame.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)),
  );
  // FR-07.2 hard gates: approval + license. Điểm cao không bù được vi phạm.
  const allowed = scoped.filter((p) => p.status === "approved" && (p.license_status === "own_authored" || p.license_status === "allowed"));

  const journal = JOURNALS.find((j) => j.journal_id === req.journal_id);
  let fallback_tier: RecommendationResponse["fallback_tier"] = "generic";
  let fallback_reason: string | undefined = "No journal or field specified; generic patterns are used.";
  if (journal) {
    const fp = journal.fingerprints.find((f) => !req.genre || f.genre === req.genre);
    if (fp && fp.confidence !== "low") {
      fallback_tier = "journal_genre";
      fallback_reason = undefined;
    } else {
      fallback_tier = "field";
      fallback_reason = `The profile for “${journal.title}” has N = ${fp?.sample_n ?? 0}, below threshold; falling back to ${journal.field}.`;
    }
  } else if (req.field) {
    fallback_tier = "field";
    fallback_reason = `No journal specified; ranked by field (${req.field}).`;
  }

  const candidates: Candidate[] = allowed
    .map((p) => {
      const breakdown = {
        intent_section: req.intent_id || req.section ? 0.95 : 0.7,
        disciplinary_fit: req.field || journal ? 0.75 : 0.6,
        journal_genre: fallback_tier === "journal_genre" ? 0.8 : 0.5,
        evidence_alignment: p.epistemic_strength === "moderate" ? 0.85 : p.epistemic_strength === "low" ? 0.9 : 0.6,
        linguistic_quality: 0.85,
        provenance_confidence: p.provenance === "authored" ? 0.9 : 0.75,
      };
      const score = Object.entries(breakdown).reduce((s, [k, v]) => s + v * WEIGHTS[k as keyof typeof WEIGHTS], 0);
      const intent = INTENTS.find((i) => i.intent_id === p.intent_id);
      return {
        pattern: p, score, rank: 0, breakdown,
        explanation: `Matches the intent “${intent?.name}” in ${p.section_scope.join(" / ")}; ${p.epistemic_strength} epistemic strength.`,
      };
    })
    .sort((a, b) => b.score - a.score)
    .map((c, i) => ({ ...c, rank: i + 1 }));

  return {
    request_id: `req-${Date.now().toString(36)}`,
    candidates,
    fallback_tier,
    fallback_reason,
    gated_out: scoped.length - allowed.length,
    rule_version: "rank-w0.1",
  };
}

const STRONG = /\b(prove[sd]?|demonstrates?|demonstrated|establish(es|ed)?|confirms?|clearly shows?)\b/gi;
const MEDIUM = /\b(indicates?|shows?|reveals?)\b/gi;
const FABRICATION = /\b(10\.\d{4,}\/\S+|et al\.,? \d{4}|\(\w+,? \d{4}\)|\d+(\.\d+)?\s?%)/g;
const ABSOLUTE = /\b(no (prior )?(study|studies|work) has ever|never been (studied|investigated))\b/gi;

export function validate(req: ValidationRequest): ValidationResult {
  const v: Violation[] = [];
  const text = req.text;
  const level = STRENGTH_RANK[req.evidence_level];

  for (const m of text.matchAll(STRONG)) {
    if (level < 2)
      v.push({
        code: "V02", severity: level === 0 ? "block" : "warn", kind: "scientific",
        message: `“${m[0]}” overstates the available evidence (${req.evidence_level}).`,
        location: { start: m.index!, end: m.index! + m[0].length },
        recommended_action: level === 0 ? "Use “may” or “suggest”" : "Use “indicate” or “suggest”",
      });
  }
  for (const m of text.matchAll(MEDIUM)) {
    if (level === 0)
      v.push({
        code: "V02", severity: "warn", kind: "scientific",
        message: `“${m[0]}” is somewhat strong for low evidence.`,
        location: { start: m.index!, end: m.index! + m[0].length },
        recommended_action: "Downgrade to “suggest” or add a hedge",
      });
  }
  if (req.evidence_ids.length === 0) {
    for (const m of text.matchAll(FABRICATION))
      v.push({
        code: "V03", severity: "block", kind: "scientific",
        message: `“${m[0]}” appears to be a citation or figure, but no evidence is linked.`,
        location: { start: m.index!, end: m.index! + m[0].length },
        recommended_action: "Link real evidence or replace with a {statistic} / {citation} placeholder",
      });
  }
  for (const m of text.matchAll(ABSOLUTE))
    v.push({
      code: "V03", severity: "block", kind: "scientific",
      message: "An absolute gap claim requires an exhaustive systematic search.",
      location: { start: m.index!, end: m.index! + m[0].length },
      recommended_action: "Use “few studies have addressed…” supported by a literature synthesis",
    });
  for (const m of text.matchAll(/\{[a-z_]+\}/g))
    v.push({
      code: "V03", severity: "warn", kind: "scientific",
      message: `Slot ${m[0]} is unfilled.`,
      location: { start: m.index!, end: m.index! + m[0].length },
      recommended_action: "Provide real content; the system does not generate it (BR-02)",
    });

  const journal = JOURNALS.find((j) => j.journal_id === req.journal_id);
  if (journal) {
    if (journal.guidelines.length === 0) {
      v.push({ code: "V08", severity: "warn", kind: "policy", message: `“${journal.title}” has no verified guidelines; only generic checks were applied.`, recommended_action: "Do not infer requirements from corpus statistics" });
    }
    const noI = journal.guidelines.find((g) => g.rule_id === "G-2");
    const iMatch = /\bI\b/.exec(text);
    if (noI && iMatch)
      v.push({
        code: "V05", severity: "block", kind: "policy", message: noI.text,
        location: { start: iMatch.index, end: iMatch.index + 1 },
        recommended_action: "Use “we” or the passive voice",
        source: `${journal.title} guideline v${journal.guideline_version} (verified ${noI.verified_at})`,
      });
  }

  const words = text.toLowerCase().match(/\b[a-z]{5,}\b/g) ?? [];
  const counts = new Map<string, number>();
  words.forEach((w) => counts.set(w, (counts.get(w) ?? 0) + 1));
  for (const [w, n] of counts)
    if (n >= 3) v.push({ code: "V07", severity: "warn", kind: "language", message: `“${w}” is repeated ${n} times.`, recommended_action: "Vary the wording or merge clauses" });

  if (text.split(/\s+/).filter(Boolean).length > 45)
    v.push({ code: "V06", severity: "warn", kind: "language", message: "The sentence exceeds 45 words.", recommended_action: "Split into two sentences" });

  const verdict = v.some((x) => x.severity === "block") ? "block" : v.length ? "warn" : "pass";
  let suggestion: string | undefined;
  if (v.some((x) => x.code === "V02"))
    suggestion = text.replace(STRONG, (w) => {
      if (level === 0) return "may suggest";
      // Giữ dạng ngôi 3 số ít / quá khứ của động từ gốc: prove → indicate, proves → indicates.
      if (/ed$/i.test(w)) return "indicated";
      return /s$/i.test(w) ? "indicates" : "indicate";
    });
  return { verdict, violations: v, suggestion };
}
