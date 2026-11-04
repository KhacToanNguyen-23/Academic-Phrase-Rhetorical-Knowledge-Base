# ADR-0007: Runtime rule-based mining

Status: Accepted; owner decision 2026-10-31.

Enable regex-based sentence slot extraction in the existing worker. Keep pending candidates, two-round review, provenance and license checks; mining does not write patterns or versions. Use typed public slot schemas and private source offsets. Runtime configuration uses fixed conservative spans and positional names; unreviewed aliases and uncertain contexts remain separate. No new endpoints.

spaCy runs at ingest behind `NLP_ENGINE` to provide rule-first sentence boundaries and stored token features (ADR-0010). Phase 3 lets `SentenceFilter` and `SlotAbstractor` consume valid stored features with a regex fallback for missing/invalid data; NER, production classifiers, embeddings and LLM remain deferred. Tests use self-authored mock data. There has been no quality evaluation on real data. Gold, evaluator and tuning await the external article API; future gold is sampled from real articles, with two editors, reported disagreement and adjudication under FR-06.6. The prior held-out proposal is superseded. No extra human role or gate is required for this runtime increment.

Candidate private JSONB occurrence metadata is an intentional deviation from the separate occurrence entity in System Design. Existing legacy rows remain nullable and are not backfilled.

## Deferred decision: AI suggests, humans decide (2026-10-31)

Owner direction: AI may propose labels but cannot approve, count as a review round, merge provenance automatically or write patterns/versions. The reason is to retain human editorial control before publication. PRD FR-06.3 requires reviewer confirmation; FR-06.5 requires batch decisions per item without provenance loss; System Design §9 calls for human-in-the-loop before publish. Candidate confidence already exists in SCAFFOLD_PRD §4.4; it remains null in the current rule-only increment.

**[Proposal]** After the article API and human-reviewed real-article gold exist, an optional stage following the rule stages may suggest intent, strength and confidence, mark AI as source and keep candidates pending. A reviewer accepts, edits or rejects; future batch/cluster review and confidence ordering are proposed, not implemented. For gold, AI drafts are independently checked and corrected by two editors; around 20% of sentences are labeled without AI drafts to measure AI–human κ and examine anchoring. PRD FR-06.6 requires two-editor agreement and reporting disagreement/adjudication; the AI draft and blind subset are proposals. Daily-review assistance is enabled only after measuring AI against human-checked gold.

**Open owner decisions [Proposal]:** confirm license permission for external AI processing or use a self-hosted model; `allows_mining` alone does not authorize a third party. Approve expanding LLM scope, which SCAFFOLD_PRD §14 currently defers. Never log/audit source text, prompts containing source text or API keys. Version model, prompt and thresholds in policy YAML with `TODO(owner)` for provisional values. The PRD roadmap lists AI-assisted annotation as deferrable at M1. The earlier committed SCAFFOLD_PRD §14 described the order “luật → NER khoa học → LLM có kiểm tra lại”; this is historical wording, not an assertion that the current §14 retains that line.

**Separate review safeguard [Proposal]:** the current review service counts decisions but does not require different reviewers. Pending owner approval, reject a repeated `reviewer_id` with HTTP 409 and add a regression test. No AI or review implementation is included in this decision.
