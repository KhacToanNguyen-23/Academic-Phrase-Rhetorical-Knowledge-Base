# Gold development labeling guideline v0

The AI proposes labels for each unchanged source sentence; one human reviewer accepts or edits the proposal and makes the final decision. These are definitions and self-written examples only; source article sentences remain in the local database.

## Fields

- `keep`: true when the sentence contains usable language for phrase mining. False for captions, table rows, formulas, references, acknowledgements, fragments, metadata or other noise.
- `noise_reason`: required only when `keep=false`; one of `caption`, `table`, `formula`, `reference`, `acknowledgement`, `fragment`, `metadata`, `other`.
- `section`: section code, or `OTHER` when unknown.
- `epistemic_strength`: `low`, `moderate`, `high`, `absolute`, or `none` when no reporting-strength marker is present.
- `tense`: tense of the main reporting predicate: `past`, `present`, `present_perfect`, or `none` when no reporting predicate applies.
- `frame`: reusable rhetorical wording with positional placeholders `[X]`, `[Y]`, `[Z]`; preserve negation, modal and comparison wording.
- `slots`: source sentence-relative half-open Unicode offsets `{name, char_start, char_end}`. Each source slice must be non-empty and in bounds.
- `ownership`: `own`, `prior` or `unclear`; use `unclear` without enough context.
- `notes`: short reviewer note; never put personal information here.

`intent` is not labeled in v0. Suggested labels are drafts. The human reviewer accepts or edits them; only human-reviewed final labels count as gold. This development workflow does not satisfy FR-06.6's separate two-editor validation requirement.

## Self-written example

Synthetic illustration: `These results suggest that seedlings tolerate cold.` A possible frame is `These results suggest that [X].`, where `[X]` spans `seedlings tolerate cold`. This illustrates offsets only and is not a gold item or expected system output.
