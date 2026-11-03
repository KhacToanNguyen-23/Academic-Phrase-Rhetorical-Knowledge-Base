// Dữ liệu mẫu tự biên soạn (own_authored) để chạy UI khi chưa có backend.
// Không sao chép Manchester Academic Phrasebank (BR-01).
import type { Intent, JournalProfile, PhrasePattern } from "./mock-types";

export const INTENTS: Intent[] = [
  { intent_id: "INT-GAP", name: "Identify research gap", move: "M2 Establish a niche", sections: ["Introduction"] },
  { intent_id: "INT-BG", name: "Establish topic importance", move: "M1 Establish territory", sections: ["Introduction"] },
  { intent_id: "INT-AIM", name: "State aim of study", move: "M3 Occupy the niche", sections: ["Introduction"] },
  { intent_id: "INT-MTH", name: "Describe procedure", move: "Method description", sections: ["Methods"] },
  { intent_id: "INT-RES", name: "Report main finding", move: "Result statement", sections: ["Results", "Discussion"] },
  { intent_id: "INT-LIM", name: "Acknowledge limitation", move: "Evaluate study", sections: ["Discussion", "Conclusion"] },
];

export const FIELDS = ["Computer Science", "Medicine", "Environmental Science", "Social Sciences"];

const own = { provenance: "authored" as const, license_status: "own_authored" as const };

export const PATTERNS: PhrasePattern[] = [
  {
    id: "GAP-014", ...own, status: "approved", version: "1.2.0",
    canonical_frame: "Although {research_focus} has been examined, its behavior under {specific_condition} remains insufficiently characterized.",
    intent_id: "INT-GAP", section_scope: ["Introduction"], article_genres: ["Original Research", "SLR"],
    claim_type: "gap", epistemic_strength: "moderate",
    slots_schema: [
      { name: "research_focus", type: "concept", guidance: "A topic already addressed in the literature", required: true },
      { name: "specific_condition", type: "concept", guidance: "A condition not yet examined", required: true },
    ],
    constraint: {
      evidence_min: "A literature synthesis showing limited work under this condition",
      forbidden_contexts: ["No literature review available", "Speculative gap"],
      guidance: "“Insufficiently characterized” must be supported by a literature synthesis.",
    },
    variants: [
      { variant_id: "GAP-014-v1", phrase_text: "Despite growing work on {research_focus}, little is known about its behavior under {specific_condition}.", transformation: "Concessive restructuring", semantic_status: "equivalent" },
      { variant_id: "GAP-014-v2", phrase_text: "Evidence on {research_focus} under {specific_condition} remains limited.", transformation: "Condensed", semantic_status: "pending_review" },
    ],
    provenance_note: "Authored by the language editor, Sept. 2026",
    corpus_support: { occurrences: 42, documents: 31, window: "2019–2025" },
  },
  {
    id: "GAP-021", ...own, status: "approved", version: "1.0.0",
    canonical_frame: "To date, few studies have addressed {topic} in {population_or_setting}.",
    intent_id: "INT-GAP", section_scope: ["Introduction"], article_genres: ["Original Research", "SLR", "Review"],
    claim_type: "gap", epistemic_strength: "moderate",
    slots_schema: [
      { name: "topic", type: "concept", guidance: "Topic", required: true },
      { name: "population_or_setting", type: "concept", guidance: "Population or setting", required: true },
    ],
    constraint: { evidence_min: "A documented search strategy or systematic review", forbidden_contexts: ["No literature search performed"], guidance: "“Few” must reflect actual search results." },
    variants: [], provenance_note: "Authored by the language editor, Sept. 2026",
  },
  {
    id: "GAP-030", provenance: "corpus_inferred", license_status: "allowed", status: "approved", version: "1.0.0",
    canonical_frame: "It remains unclear whether {mechanism} contributes to {outcome}.",
    intent_id: "INT-GAP", section_scope: ["Introduction", "Discussion"], article_genres: ["Original Research"],
    claim_type: "gap", epistemic_strength: "low",
    slots_schema: [
      { name: "mechanism", type: "concept", guidance: "Hypothesised mechanism", required: true },
      { name: "outcome", type: "concept", guidance: "Outcome of interest", required: true },
    ],
    constraint: { evidence_min: "At least one source indicating uncertainty", forbidden_contexts: [], guidance: "Low hedge; safe when evidence is thin." },
    variants: [], provenance_note: "Mined from an open-access corpus (CC BY); reviewed by two editors",
    corpus_support: { occurrences: 118, documents: 96, window: "2018–2025" },
  },
  {
    id: "GAP-033", ...own, status: "in_review", version: "0.3.0",
    canonical_frame: "No prior work has ever investigated {topic}.",
    intent_id: "INT-GAP", section_scope: ["Introduction"], article_genres: ["Original Research"],
    claim_type: "gap", epistemic_strength: "high",
    slots_schema: [{ name: "topic", type: "concept", guidance: "Topic", required: true }],
    constraint: { evidence_min: "An exhaustive systematic search", forbidden_contexts: ["Any context without a systematic review"], guidance: "Absolute claim." },
    variants: [], provenance_note: "Draft",
  },
  {
    id: "BG-003", ...own, status: "approved", version: "1.1.0",
    canonical_frame: "{phenomenon} has become a central concern in {field} because {reason}.",
    intent_id: "INT-BG", section_scope: ["Introduction"], article_genres: ["Original Research", "Review"],
    claim_type: "background", epistemic_strength: "moderate",
    slots_schema: [
      { name: "phenomenon", type: "concept", guidance: "Phenomenon", required: true },
      { name: "field", type: "concept", guidance: "Field", required: true },
      { name: "reason", type: "text", guidance: "A referenced rationale", required: true },
    ],
    constraint: { evidence_min: "At least one citation for {reason}", forbidden_contexts: [], guidance: "Do not invent illustrative figures." },
    variants: [], provenance_note: "Authored by the language editor, Aug. 2026",
  },
  {
    id: "AIM-002", ...own, status: "approved", version: "1.0.0",
    canonical_frame: "This study aims to {objective} by {approach}.",
    intent_id: "INT-AIM", section_scope: ["Introduction"], article_genres: ["Original Research"],
    claim_type: "method", epistemic_strength: "moderate",
    slots_schema: [
      { name: "objective", type: "text", guidance: "Objective (infinitive verb phrase)", required: true },
      { name: "approach", type: "text", guidance: "Approach", required: true },
    ],
    constraint: { evidence_min: "None", forbidden_contexts: [], guidance: "The objective must match the research question." },
    variants: [], provenance_note: "Authored by the language editor, Aug. 2026",
  },
  {
    id: "RES-010", ...own, status: "approved", version: "2.0.0",
    canonical_frame: "The results indicate that {finding} ({statistic}).",
    intent_id: "INT-RES", section_scope: ["Results", "Discussion"], article_genres: ["Original Research"],
    claim_type: "result", epistemic_strength: "moderate",
    slots_schema: [
      { name: "finding", type: "text", guidance: "Principal finding", required: true },
      { name: "statistic", type: "number", guidance: "A statistic from actual results — never invented", required: true },
    ],
    constraint: { evidence_min: "Analysed results with statistics", forbidden_contexts: ["Unanalysed results"], guidance: "“Indicate” suits moderate evidence." },
    variants: [{ variant_id: "RES-010-v1", phrase_text: "Our analysis suggests that {finding} ({statistic}).", transformation: "Softer hedge", semantic_status: "equivalent" }],
    provenance_note: "Authored by the language editor, Sept. 2026",
  },
  {
    id: "RES-012", provenance: "corpus_inferred", license_status: "restricted", status: "approved", version: "1.0.0",
    canonical_frame: "These findings demonstrate that {finding}.",
    intent_id: "INT-RES", section_scope: ["Results"], article_genres: ["Original Research"],
    claim_type: "result", epistemic_strength: "high",
    slots_schema: [{ name: "finding", type: "text", guidance: "Finding", required: true }],
    constraint: { evidence_min: "Strong evidence (RCT or replication)", forbidden_contexts: [], guidance: "" },
    variants: [], provenance_note: "Restricted corpus — quarantined",
  },
  {
    id: "LIM-004", ...own, status: "approved", version: "1.0.0",
    canonical_frame: "A limitation of this study is that {limitation}, which may affect {consequence}.",
    intent_id: "INT-LIM", section_scope: ["Discussion", "Conclusion"], article_genres: ["Original Research", "SLR"],
    claim_type: "limitation", epistemic_strength: "low",
    slots_schema: [
      { name: "limitation", type: "text", guidance: "Limitation", required: true },
      { name: "consequence", type: "text", guidance: "Effect on conclusions", required: true },
    ],
    constraint: { evidence_min: "None", forbidden_contexts: [], guidance: "Be specific; avoid generic statements." },
    variants: [], provenance_note: "Authored by the language editor, Sept. 2026",
  },
];

export const JOURNALS: JournalProfile[] = [
  {
    journal_id: "J-001", issn_l: "1234-5678", title: "Journal of Applied Computing Research", publisher: "Example Academic Press",
    field: "Computer Science", guideline_url: "https://example.org/jacr/author-guidelines", guideline_version: "2026.1", retrieved_at: "2026-10-12",
    guidelines: [
      { rule_id: "G-1", level: "required", text: "Structured abstract (Background, Methods, Results, Conclusions), max. 250 words.", source_excerpt: "Section 3.2 — Abstract", verified_at: "2026-10-12", reviewer: "analyst.lan" },
      { rule_id: "G-2", level: "required", text: "First-person singular (“I”) must not be used.", source_excerpt: "Section 4.1 — Style", verified_at: "2026-10-12", reviewer: "analyst.lan" },
      { rule_id: "G-3", level: "recommended", text: "Active voice is preferred.", source_excerpt: "Section 4.1 — Style", verified_at: "2026-10-12", reviewer: "analyst.lan" },
    ],
    fingerprints: [{
      genre: "Original Research", date_range: "2021–2025", sample_n: 184, confidence: "high", method_version: "fp-0.4",
      features: [
        { name: "Hedging density", journal_value: 6.1, field_baseline: 7.4, unit: "per 1k words" },
        { name: "Passive voice (Methods)", journal_value: 38, field_baseline: 52, unit: "%" },
        { name: "Mean sentence length", journal_value: 22.4, field_baseline: 24.9, unit: "words" },
        { name: "First-person plural (“we”)", journal_value: 71, field_baseline: 58, unit: "% of articles" },
      ],
    }],
  },
  {
    journal_id: "J-002", issn_l: "8765-4321", title: "Environmental Systems Letters", publisher: "Example Society",
    field: "Environmental Science",
    guidelines: [],
    fingerprints: [{
      genre: "Original Research", date_range: "2023–2025", sample_n: 17, confidence: "low", method_version: "fp-0.4",
      features: [
        { name: "Hedging density", journal_value: 8.2, field_baseline: 7.9, unit: "per 1k words" },
        { name: "Mean sentence length", journal_value: 26.0, field_baseline: 25.1, unit: "words" },
      ],
    }],
  },
];
