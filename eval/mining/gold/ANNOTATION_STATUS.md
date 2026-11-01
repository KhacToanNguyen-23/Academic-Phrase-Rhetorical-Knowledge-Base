# Annotation status — Gold dev v0

Status: sampling complete; annotation and AI labeling have not started.

- A deterministic 300-item sample from real SLR articles exists in the local database, with 90 items assigned to `test`.
- No AI drafts, human labels, scores, approvals, κ values or quality claims have been created.
- The selected development workflow has one final human reviewer for all AI-labeled items. It does not satisfy FR-06.6's separate two-editor validation requirement.
- AI labeling has not started. Mock tests need no key; a real Groq run requires owner direction and a local `.env` key. `TODO(owner, BR-10)` remains for unclear third-party processing rights.

Do not place article text, prompts, responses, provider keys or annotator names/emails in this file or the repository.
