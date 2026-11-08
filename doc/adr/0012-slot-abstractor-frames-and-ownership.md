# ADR-0012: Closed reporting frames and conservative ownership

- Status: implemented for phases 6 and 7; policy lists remain provisional where marked.
- Date: 2026-11-05
- Requirements: FR-05, FR-06.2.

## Context

Phase 6 fixes syntax-path frames that selected a regex-located verb, silently dropped
lead-ins/citations, or absorbed unreviewed words into slots. Ownership also treated `we`
as unclear and inferred determiner ownership without the contextual evidence required by
FR-05.

## Decisions

1. A syntax frame represents the whole sentence with slot spans replaced. The reporting
   ROOT and its located auxiliary, negation and approved modifier group define the verb
   group. `that` remains literal. The syntax path never re-runs the regex locator to choose
   a frame verb; the regex path retains its existing frame rendering.
2. Text outside slots and the verb group is closed-world. A lead-in is allowed only when
   it matches the versioned `lexicon/lead_ins.yaml` list after trimming, dropping one
   trailing comma and case-folding. It is kept literally. All other unexplained content
   is rejected with a counted reason. Do not grow this list from mining data.
3. Between subject and ROOT, only auxiliaries, negation and adverbs may occur. Adverbs are
   literal only when listed in `slot_abstraction.yaml: verb_modifiers`; otherwise reject
   with `unlisted_modifier`. Between ROOT and the `that` marker only whitespace is allowed.
   After the clause slot, only citation signals (which extend the slot) and final punctuation
   are allowed. Direct citations after a subject likewise extend that subject slot.
4. Tense and modality are separate. `Tense` includes `past_perfect`; modal + `have` + a
   participle is `present_perfect`, modal alone is `present`, and the modal word is recorded
   in `MiningItem.modality`. Modality does not enter `cluster_key` because it remains literal
   in the frame. Modality is not persisted yet.
5. Ownership is shared between reporting extraction and `ConstructionMatcher`. A subject
   beginning with `we` is always OWN. `our`, `the present` and `the current` are unconditional
   DET_OWN; `this` with `paper`, `study` or `article` is also unconditional DET_OWN. Tier B
   pairs (`these results/findings`, `this result/finding/method/approach/model/work`) are
   DET_OWN only when there is no previous-sentence citation or prior-work cue and the current
   section is not INTRO or RELATED_WORK. Missing previous text or section is not a blocker.
   `these studies` and `these authors` are DET_PRIOR. Other determiner+noun pairs, including
   `this phenomenon`, keep the determiner literal inside one noun-phrase slot and remain
   UNCLEAR. Existing prior determiners and citation/`et al.` precedence remain; a citation
   or `et al.` in the subject forces PRIOR. All ownership tiers are provisional:
   TODO(owner, FR-06.2). The former `own_study_cues` list was removed; Tier B now uses the
   section guard and the shared prior-work/citation blocker only.
6. Keep the current sentence-level `cluster_key`. This phase does not add `frame_key` or
   merge forms such as `show`/`shows`. Tense and ownership remain key dimensions as before.
7. The epistemic tagger runs after reporting/construction extraction and reads the masked
   frame, so slot content cannot set strength. It applies `irregular_forms` at the strength
   of the base marker. `show/shows/showed/shown`, `find/finds/found`, `observe/observes/
   observed`, `note/notes/noted`, and `assume/assumes/assumed` have neutral status and no
   strength. `demonstrate`, `confirm` and `establish` are high; `suggest` and `indicate`
   remain moderate; `prove` remains absolute; low markers remain low. `MiningItem` records
   `epistemic_status` as assigned, neutral, ambiguous or unknown. Status does not enter
   `cluster_key` and is not persisted. Strength remains separate and unchanged apart from
   `show` moving to neutral. `assume` is a provisional neutral reporting-class member:
   TODO(owner, FR-06.2).
   `show` is neutral for mining only. V02 still enforces it as `high` through
   `validator_only_markers`; `establish` is `mining_only_markers`. Shared `markers` affect
   both consumers, so scope-specific changes belong in the scoped lists.

## Consequences and limits

- The lead-in list was owner-approved for phase 6. The verb modifier list, ownership tiers,
  and neutral-verb list remain provisional and carry `TODO(owner, FR-06.2)`.
- Syntax rejections are counted by reason; source text and token text remain absent from logs.
- Regex behavior with `tokens=None` remains unchanged except for the explicit FR-05 ownership
  changes. Syntax behavior changes are checked with self-authored fixtures, not treated as
  a real-corpus quality measurement.
- Modality is an in-memory mining attribute only. No database column or OpenAPI contract is
  introduced.

The phase-6 implementation report is [here](../../plans/reports/261105-spacy-phase6-report.md),
and the phase-7 implementation report is [here](../../plans/reports/261105-spacy-phase7-report.md).
