# Spec: Runtime mining slot abstraction

Owner decision: 2026-10-31. G1 is approved. Implement the existing upload/import → ingest → mine_article → stages → pending Candidate → two-round review flow. Mining does not create patterns or versions and adds no endpoint. New extraction is enabled. The two review rounds and pending status remain the safety boundary.

## Extraction and privacy

Use sentence units, fixed conservative spans and positional slot names. The regex baseline preserves source offsets and citations, negation, comparison and modal signals; deterministic priority handles citations, numbers, percentages, units, years and acronyms. Keep unrecognized wording. spaCy syntax and NER are deferred: TODO(owner, FR-06.2). Do not claim comprehensive entity masking or quality evaluation. Private extraction metadata holds per-occurrence sentence IDs and source ranges, not raw originals. Public slots contain only typed reusable schema. No source text in logs, audit or API. Candidate confidence remains null, intent classifier remains TODO(owner, FR-06.3), and copyright quality flags remain TODO(owner, FR-06.4).

Recheck current allows_mining before loading source sentences. Build one previous-sentence context from original ordering within the same known section before filtering. A cited or prior-study sentence blocks contextual ownership; section label alone does not establish ownership. Own-study cues may establish ownership for this/these/the only without blockers. Preserve source occurrences and do not consolidate incompatible ownership or span contexts.

## Conservative grouping

Separate different reporting tenses, effective strength, ownership, complements, protected signals and slot bindings. Normalize only reviewed reporting verb synonym classes in reporting_verbs.yaml and reviewed DET_OWN/DET_PRIOR determiner rules. Unknown or uncertain inputs retain literal wording and do not create nonliteral equivalence. Do not guess classifier output. Use deterministic version-namespaced SHA-256 cluster keys within 255 characters, retaining independent candidate surface variants. No family_id.

## Verification and deferred work

Use only self-authored synthetic unit fixtures and upload/ingest/mine integration, including negative tense/strength/ownership pairs and source offset checks. No real quality claims. Gold, evaluator, tuning and quality evaluation are deferred until the external article API exists; sample future gold from actual articles, with two editors, reported disagreement and adjudication under FR-06.6. Do not invent gold or approvals. Phase 08 held-out plan is superseded. The only entry gate for runtime phases is approved G1.

## AI assistance (deferred)

AI suggests only; humans make final decisions. AI does not approve, count as a review round, automatically merge provenance, or write patterns/versions. **[Proposal; PRD FR-06.3/06.5; System Design §9]** A future optional stage after rule stages suggests intent, strength and confidence, marks AI as the source and leaves candidates pending; reviewers may accept, edit or reject, with batch/cluster review and confidence ordering proposed. The current increment retains `confidence = null`; no AI feature is implemented. **[Proposal; existing confidence field: SCAFFOLD_PRD §4.4]**

After the article API exists, future gold comes from sampled real articles. AI proposes draft labels, two editors independently review/correct, and approximately 20% of sentences are labeled without seeing the draft to measure AI–human κ and examine anchoring. This procedure is **[Proposal]**; PRD FR-06.6 requires two-editor agreement, reported disagreement and adjudication. Enable daily-review AI suggestions only after measuring AI against human-checked gold. No gold or scores are asserted.

Open owner decisions before enablement: verify license permission for external AI processing or use a self-hosted model; `allows_mining` alone is insufficient for third-party processing. Exclude source sentences, prompts containing them, and API keys from logs/audit; version model, prompt and thresholds in `apps/backend/src/aprkb/policies/` YAML and mark provisional values `TODO(owner)`. Owner approval is required for LLM scope, currently deferred in SCAFFOLD_PRD §14. **[Proposal]** The PRD roadmap treats AI-assisted annotation as deferrable in M1. The earlier committed §14 described “luật → NER khoa học → LLM có kiểm tra lại”; current §14 defers NER/LLM.

The review service currently counts decisions without requiring distinct reviewers. A separate owner-approval-pending proposal would reject a repeated `reviewer_id` with HTTP 409 and add a test. No review code changes are included. **[Proposal]**
