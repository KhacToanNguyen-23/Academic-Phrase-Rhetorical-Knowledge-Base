# Plan: Mining slot abstraction

Date: 2026-10-31
Risk: high-risk — source privacy, persistence and migration.
Status: Owner redirected the work to runtime phases 04–06 with TDD; G1 approved.

## Scope and gates

G1: limited M2 scope approved and documented. It is the only entry gate for phases 04–06, implemented in that order. Upload/import → ingest → worker mine_article → stages → pending Candidate → two-round review. Mining never writes patterns or versions. No new endpoints or OpenAPI changes. The planned implementation enables the new extraction in the worker.

Use self-authored mock fixtures and an upload/ingest/mine integration test. Gold, editor annotation, evaluator, tuning and quality evaluation are deferred until the external article API exists; gold will be sampled from real articles. FR-06.6 requires two editors, disagreement reporting and adjudication. No extra role or evaluation gate is imposed now. No gold, scores or approvals are fabricated.

| Phase | Status |
|---|---|
| 01, 02, 03, 07, 09 | Deferred — awaiting article API |
| 04 | Pending — partial implementation reverted at user request |
| 05 | Pending — regex sentence extraction; spaCy deferred TODO(owner, FR-06.2) |
| 06 | Pending — conservative keys and worker integration |
| 08 | Superseded — future gold sampled from real articles replaces held-out plan |
| [10 — AI-assisted labeling](phase-10-ai-assisted-labeling.md) | Deferred — awaiting article API, human-reviewed gold and owner approval of LLM scope |

## Runtime requirements

Preserve source provenance privately, use typed public slot schemas, keep confidence null, recheck allows_mining before reading sentences, and never expose source text in logs, audit or API. Use fixed conservative spans and positional names. Distinguish tense, strength, ownership and complement; normalize only reviewed synonym classes and guarded DET_OWN/DET_PRIOR. Unknowns retain literal wording and split on uncertainty. No family_id, prefix unit, alternate span/naming experiments or two-environment CI.

Verify with TDD, self-authored negative pairs and upload integration, lint and tests. Follow the current Alembic head without editing existing migrations. Keep source/import changes untouched. No commits.

## Owner actions

External article API and future real-article sampling and FR-06.6 evaluation are deferred; no staffing or protocol freeze blocks this implementation.

### Deferred AI assistance — owner decisions still open

AI may suggest, but a human makes every final decision. AI cannot approve, count as a review round, merge provenance automatically, or write a pattern/version. **[Proposal; PRD FR-06.3/06.5; System Design §9 human-in-the-loop]** In this increment, Phase 04–06 remain rule-based and `Candidate.confidence` remains null; the existing field is specified in SCAFFOLD_PRD §4.4.

**[Proposal]** A future optional stage after the rule stages in `mine_article` suggests intent, strength and confidence, marks the suggestion source as AI and keeps the candidate pending. Reviewers accept, edit or reject, with batch/cluster review and confidence ordering proposed for future work; these are not current API capabilities. FR-06.5 requires per-item decisions and retained provenance. **[Proposal]** For gold sampled from real articles, AI drafts labels, then two editors independently check and correct them. Approximately 20% of sentences are annotated by editors without seeing AI drafts; compare AI and human labels with κ on this subset and examine anchoring bias. Do not claim a result until measured. Two-editor agreement, disagreement and adjudication are required by FR-06.6; AI drafts, the 20% subset and AI–human κ are proposals.

Daily-review AI suggestions are enabled only after measuring AI against human-checked gold. The owner still must decide: whether source licenses permit sending sentences to an external AI provider or a self-hosted model will be used (`allows_mining` alone does not grant third-party processing); and whether to approve the scope expansion for LLM, currently deferred in SCAFFOLD_PRD §14. Do not log/audit source sentences, prompts containing them, or API keys. Model, prompt and thresholds must be versioned in YAML under `apps/backend/src/aprkb/policies/`, with provisional values marked `TODO(owner)`. These operational requirements are **[Proposal]**. No AI calls or implementation are included now.

**Review gap [Proposal]:** `apps/backend/src/aprkb/modules/review/service.py` counts decisions but does not require different reviewers for the two rounds. Propose a separate change returning HTTP 409 when `reviewer_id` matches an earlier round, with a regression test; await owner approval. It is not implemented here.

Source traceability: PRD FR-06.3 requires confidence and reviewer confirmation; FR-06.5 specifies batch decisions per item and provenance; FR-06.6 specifies two-editor agreement, disagreement and adjudication. The PRD roadmap lists AI-assisted annotation as deferrable at M1. System Design §9 places humans in the loop before publishing. The earlier committed SCAFFOLD_PRD §14 described the order “luật → NER khoa học → LLM có kiểm tra lại”; current §14 defers NER and LLM, so LLM scope still requires owner approval. This historical citation is to §14, not §2 or a line number.

## Session Notes

The partial Phase 04–06 code and migration were reverted at the user's request. The existing worker can still expose its original unmasked candidate frame via the review API; the planned privacy boundary is not yet implemented. No new extraction is enabled.
