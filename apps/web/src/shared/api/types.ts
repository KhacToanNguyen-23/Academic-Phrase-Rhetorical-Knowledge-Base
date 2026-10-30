// Type tạm thời viết tay theo PRD-11 / System Design §4.2.
// Khi backend xuất openapi.json, thay bằng type sinh từ `pnpm gen:api` (ADR-0004) và xoá file này.

export type PatternStatus = "draft" | "in_review" | "approved" | "retired";
export type LicenseStatus = "own_authored" | "allowed" | "restricted" | "unknown";
export type Provenance = "authored" | "adapted_permission" | "corpus_inferred"; // FR-02.7
export type ClaimType = "background" | "gap" | "method" | "result" | "implication" | "limitation";
export type EpistemicStrength = "low" | "moderate" | "high";
export type Section = "Introduction" | "Methods" | "Results" | "Discussion" | "Conclusion";
export type Genre = "Original Research" | "SLR" | "Review";
export type FallbackTier = "journal_genre" | "similar_journal" | "subfield" | "field" | "generic"; // FR-07.4
export type EvidenceClass = "required" | "observed" | "suggested"; // BR-04, BR-09, Gate C

export interface SlotDef {
  name: string;
  type: "text" | "citation" | "number" | "concept";
  guidance: string;
  required: boolean;
}

export interface UsageConstraint {
  evidence_min: string;
  forbidden_contexts: string[];
  guidance: string;
}

export interface PhraseVariant {
  variant_id: string;
  phrase_text: string;
  transformation: string;
  semantic_status: "equivalent" | "pending_review";
}

export interface Intent {
  intent_id: string;
  name: string;
  move: string;
  sections: Section[];
}

export interface PhrasePattern {
  id: string;
  canonical_frame: string;
  intent_id: string;
  section_scope: Section[];
  article_genres: Genre[];
  claim_type: ClaimType;
  epistemic_strength: EpistemicStrength;
  slots_schema: SlotDef[];
  constraint: UsageConstraint;
  variants: PhraseVariant[];
  provenance: Provenance;
  provenance_note: string;
  license_status: LicenseStatus;
  status: PatternStatus;
  version: string;
  corpus_support?: { occurrences: number; documents: number; window: string };
}

export interface RecommendationRequest {
  query?: string;
  section?: Section;
  intent_id?: string;
  genre?: Genre;
  field?: string;
  journal_id?: string;
  claim_type?: ClaimType;
}

export interface ScoreBreakdown {
  intent_section: number;
  disciplinary_fit: number;
  journal_genre: number;
  evidence_alignment: number;
  linguistic_quality: number;
  provenance_confidence: number;
}

export interface Candidate {
  pattern: PhrasePattern;
  score: number;
  rank: number;
  breakdown: ScoreBreakdown;
  explanation: string;
}

export interface RecommendationResponse {
  request_id: string;
  candidates: Candidate[];
  fallback_tier: FallbackTier;
  fallback_reason?: string;
  gated_out: number;
  rule_version: string;
}

export interface GuidelineRule {
  rule_id: string;
  level: "required" | "recommended" | "optional";
  text: string;
  source_excerpt: string;
  verified_at: string;
  reviewer: string;
}

export interface FingerprintFeature {
  name: string;
  journal_value: number;
  field_baseline: number;
  unit: string;
}

export interface JournalFingerprint {
  genre: Genre;
  date_range: string;
  sample_n: number;
  confidence: "low" | "medium" | "high";
  method_version: string;
  features: FingerprintFeature[];
}

export interface JournalProfile {
  journal_id: string;
  issn_l: string;
  title: string;
  publisher: string;
  field: string;
  guideline_url?: string;
  guideline_version?: string;
  retrieved_at?: string;
  guidelines: GuidelineRule[];
  fingerprints: JournalFingerprint[];
}

export type Severity = "pass" | "warn" | "block";

export interface Violation {
  code: "V01" | "V02" | "V03" | "V04" | "V05" | "V06" | "V07" | "V08";
  severity: Exclude<Severity, "pass">;
  kind: "scientific" | "language" | "policy"; // FR-08.3: tách language vs scientific risk
  message: string;
  location?: { start: number; end: number };
  recommended_action: string;
  source?: string;
}

export interface ValidationRequest {
  text: string;
  section?: Section;
  claim_type?: ClaimType;
  evidence_level: EpistemicStrength;
  evidence_ids: string[];
  journal_id?: string;
}

export interface ValidationResult {
  verdict: Severity;
  violations: Violation[];
  suggestion?: string;
}
