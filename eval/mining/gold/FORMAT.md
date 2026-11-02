# Gold development format v0 — Sampling complete, labeling pending

The schema and 300-item sample are in place. The development set is sampled from real SLR articles, not written by editors. Source sentences stay in the local corpus database; this directory contains no article text, labels, scores or human approvals. AI labeling and one-human final review are pending.

## Item and label fields

- `keep`: whether the sentence is clean running prose (not noise). It does not mean a slot can be extracted; see GUIDELINE.md v1.
- `noise_reason`: required only when `keep=false`.
- `section`: section code or `OTHER`.
- `epistemic_strength`: `low`, `moderate`, `high`, `absolute` or `none`.
- `tense`: `past`, `present`, `present_perfect` or `none`.
- `frame`: reusable rhetorical wording with positional placeholders.
- `slots`: source-sentence-relative half-open Unicode character offsets.
- `ownership`: `own`, `prior` or `unclear`.
- `notes`: short annotation note; no personal information.

The AI draft and the human-reviewed final labels are distinct. AI labels every sampled item, and one human reviewer reviews every AI draft. Only the human-reviewed final labels count as gold.

The development sample target is approximately 300 real sentences with a fixed seed and a 30% test split. The owner selected one final human reviewer for this development workflow. It does not satisfy FR-06.6's separate validation requirement for two editors, disagreement reporting and adjudication. No inter-editor agreement score or quality claim is available for this set.
