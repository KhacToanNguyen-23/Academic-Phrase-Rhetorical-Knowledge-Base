# Phase 10 — AI-assisted labeling

Status: Deferred — awaiting external article API, human-reviewed gold and owner approval of LLM scope. This phase does not change Phase 04–06.

AI supplies suggestions only: optional stage after rule stages suggests intent, strength and confidence, records AI as the source and leaves candidates pending. Reviewers make decisions, potentially by batch/cluster and ordered by confidence; decisions remain per item and provenance is retained. AI cannot approve, serve as a review round, merge provenance or write patterns/versions. **[Proposal; PRD FR-06.3/06.5; System Design §9]**

Future gold is sampled from real articles: AI drafts labels, two editors independently review and correct them, and approximately 20% is independently labeled without AI drafts for AI–human κ and anchoring analysis. Daily-review suggestions are enabled only after measuring AI against human-checked gold. No numbers or approvals exist yet. **[Proposal; two-editor agreement, disagreement and adjudication: PRD FR-06.6]**

Before enabling, resolve source license permission for external AI processing or use a self-hosted model; `allows_mining` alone does not authorize a third party. Do not log source sentences, prompts containing them, or API keys. Version model, prompt and thresholds in policy YAML with `TODO(owner)` on provisional values. Obtain owner approval to expand the currently deferred LLM scope. **[Proposal]**

An interface `CandidateLabelAssistant` with a null implementation, `enabled: false` and `TODO(owner, FR-06.3)` is optional future design only, analogous to the proposed `NullSynonymReviewAssistant`. **[Proposal]** No code, provider, endpoint or API change is authorized by this document.

Separately, propose rejecting a second review decision from the same `reviewer_id` with HTTP 409 and a test; the owner has not approved that change. **[Proposal; current behavior: `modules/review/service.py`]**
