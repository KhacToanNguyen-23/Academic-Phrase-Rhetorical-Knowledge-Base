# Gold development labeling guideline v2

The AI proposes labels for each unchanged source sentence; one human reviewer accepts or edits the proposal and makes the final decision. Only human-reviewed final labels count as gold. All examples below are self-written and illustrate the rules only; they are not gold items and not expected system output. Source article sentences remain in the local database.

Label each sentence on its own. The previous and next sentences are context for `ownership` only.

## 1. `keep` and `noise_reason`

`keep` answers one question: **is this sentence clean running prose?** It does not ask whether a slot can be extracted from it, and it does not ask whether the sentence is a "good" phrase. Extraction coverage is measured separately, so a clean sentence with no reporting verb is still `keep=true`.

- `keep=true`: a complete, readable sentence of ordinary scholarly prose (claims, methods, definitions, descriptions).
- `keep=false`: anything else. `noise_reason` is then required; when `keep=true` it must be empty.

| `noise_reason` | Use when the text is |
|---|---|
| `caption` | a figure, table or algorithm caption, e.g. `Figure 2: Training loss per epoch.` |
| `table` | a table row or cell list, mostly numbers, separators or `\|` |
| `formula` | an equation or mostly mathematical symbols |
| `reference` | a bibliography entry or a bare citation list |
| `acknowledgement` | thanks, funding or grant statements |
| `fragment` | not a complete sentence: a heading, a cut-off clause, or a leftover of bad sentence splitting |
| `metadata` | author names, affiliations, e-mail, journal name, copyright or licence text, keywords |
| `other` | noise that fits none of the above (use sparingly and explain in `notes`) |

A sentence that merely contains a number, a citation or a symbol is not noise by itself.

## 2. `section`

Copy the section code supplied with the sentence. Use `OTHER` when it is `OTHER` or missing. Do not guess a section from the content.

## 3. `epistemic_strength`

The strength of the claim the author makes, read from explicit marker words only. Use the first matching level; if the sentence has markers of two different levels, choose the level of the marker nearest the main verb. Ignore a marker that is negated (`does not show` carries no `high`).

| Level | Marker words (mirrors `epistemic_markers.yaml` v0.2.0, a draft list) |
|---|---|
| `low` | may, might, could, possibly, appears to |
| `moderate` | suggest, suggests, suggested, indicate, indicates, indicated, is likely |
| `high` | demonstrate, demonstrates, demonstrated, confirm, confirms, confirmed, establish, establishes, established |
| `absolute` | prove, proves, proved, proven, establish beyond doubt, always |
| `none` | no marker word is present |

The neutral reporting forms `show/shows/showed/shown`, `find/finds/found`,
`observe/observes/observed`, `note/notes/noted`, and `assume/assumes/assumed` carry no
epistemic strength. `assume` remains provisional as a reporting-class member (`TODO(owner,
FR-06.2)`).

Do not infer strength from the topic or tone. `We propose a new filter.` is `none`. Words outside the table (for example `argue`, `likely`, `clearly`) are not markers in v2: label `none` and say so in `notes` so the lexicon owner can review.

## 4. `tense`

The tense of the main finite verb that states the claim or action: `past`, `present` or `present_perfect`. Use `none` only when the sentence has no finite main verb.

## 5. `ownership`

Who is responsible for the claim or action?

- `own`: the authors of this article (`we`, `our`, `this paper`, `this study`, `the present work`).
- `prior`: other work (`previous studies`, `earlier work`, a named author, a cited result).
- `unclear`: neither is evident from the sentence and its neighbours. Prefer `unclear` to guessing. A sentence beginning `These results` follows its neighbour: if the previous sentence reports cited work, use `unclear`.

## 6. `frame` and `slots`

Only for `keep=true`. For `keep=false`, set `frame` to null and `slots` to an empty list.

**Rule: the frame is the whole sentence with each slot span replaced by its placeholder. Every character outside the slots stays exactly as written** (differences in spacing are ignored). Never reword, shorten, reorder or drop text, and never add text. The AI labeling job marks a draft whose frame does not match the sentence as failed.

- Placeholders are `[X]`, `[Y]`, `[Z]`, named in order of appearance; use between one and three.
- A slot is a contiguous span, with no overlap, that holds the sentence-specific content: a topic noun phrase, a subject, or a content clause.
- Keep the rhetorical wording outside the slots: the reporting verb, `that`, hedges, negation, modals, comparison words and connectives (`not only ... but also`, `more ... than`).
- A domain term belongs inside a slot, not in the frame, so the frame can be reused in another field.
- Prefer several narrow slots over one slot that swallows most of the sentence.
- `slots` use zero-based, end-exclusive character offsets into the target sentence. Each span must be non-empty and in bounds, and must start and end on a word boundary.

Worked examples (self-written):

1. Sentence `These results suggest that seedlings tolerate cold.`
   Frame `These results suggest that [X].` with `X` = `seedlings tolerate cold`.
2. Sentence `The pilot method is not faster than the baseline on small inputs.`
   Frame `The [X] is not faster than the [Y] on [Z].` with `X` = `pilot method`, `Y` = `baseline`, `Z` = `small inputs`. Negation and the comparison stay in the frame.
3. Sentence `We compared three calibration schemes using synthetic data.`
   Frame `We compared [X] using [Y].` with `X` = `three calibration schemes`, `Y` = `synthetic data`.

## 7. `notes`

A short reviewer note, optional. Mention an uncertain choice or an out-of-list marker word. Never put personal information here.

`intent` is not labeled in v2. This development workflow does not satisfy FR-06.6's separate two-editor validation requirement.
