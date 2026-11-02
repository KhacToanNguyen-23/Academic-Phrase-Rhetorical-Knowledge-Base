# Annotation status — Gold dev

Status (2026-11-02): sampling complete; AI labeling started on a trial of 10 items; no human review yet.

- A deterministic, stratified 300-item sample from real SLR articles exists in the local database, with 90 items assigned to `test`.
- 10 items carry AI draft labels produced under guideline v0 and prompt v0 (`status=draft`). 290 items are `pending_ai`. The 10 drafts predate guideline v1; do not approve them as gold without review, or re-label them under v1.
- Guideline v1 and prompt v1 are written but have not been run against Groq. AI drafts must now pass an automatic check that the frame equals the sentence with each slot replaced.
- No human labels, approvals, scores, κ values or quality claims exist. `eval-mining` cannot produce an official result until a human approves items.
- The selected development workflow has one final human reviewer for all AI-labeled items. It does not satisfy FR-06.6's separate two-editor validation requirement.
- A real Groq run requires owner direction and a local `.env` key. `TODO(owner, BR-10)` remains for unclear third-party processing rights.

Do not place article text, prompts, responses, provider keys or annotator names/emails in this file or the repository.
