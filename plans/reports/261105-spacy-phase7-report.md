# Slot abstractor phase 7 report

Date: 2026-11-05. Worktree: `feat/spacy-nlp-spike`, based on phase 6. All probe sentences
and fixture additions are self-authored. This report contains aggregate counts only.

## Changes

- Replaced phase 6 contextual own-study cues with four determiner+noun ownership tiers.
  Citation or `et al.` in a subject takes PRIOR precedence. Tier B is OWN only without a
  prior-work/citation blocker and outside INTRO/RELATED_WORK; missing previous text or
  section is not a blocker. `this phenomenon` and every unlisted pair remain literal and
  UNCLEAR. The shared helper is used by reporting and construction paths.
- Moved epistemic tagging after reporting/construction extraction so it scans the masked
  frame. Added `epistemic_status` in memory only. Status does not enter `cluster_key` and is
  not persisted; `epistemic_strength` keeps its existing role in the key.
- Moved `show/shows/showed/shown` to neutral, with strength `None`, per the owner's final
  decision. `demonstrate`, `confirm`, and `establish` remain high; `suggest` and `indicate`
  remain moderate per the phase 7 policy; `prove` remains absolute. Added the neutral verb
  list, including `assume`, to the epistemic policy. Mining only: V02 keeps its pre-phase-7
  behavior (see Verification notes).
- Added self-authored ownership and epistemic regressions and 28 phase 7 token snapshots.
  The earlier 57 snapshots are unchanged; after the first 26 additions, the 83-case prefix
  was also verified byte-identical when the final two cases were appended.
- Added the corpus lead-in counts to `plans/spacy-nlp-spike/backlog.md`; none were added to
  the approved lead-in policy.

## Corpus counts

Analysis used the same 51 stored articles before and after. The corpus covers one field
(federated learning). It contains one exact duplicate (FedQueue, two copies) and one partial
duplicate (two versions of a survey); these inflate per-article counts.

| Measure | Before phase 6 | Before phase 7 (phase 6) | After phase 7 |
|---|---:|---:|---:|
| Reporting extractions | 342 | 203 | 203 |
| Construction extractions | 43 | 43 | 43 |
| Dropped lead-in bug | 125 | 0 | 0 |
| Accepted lead-ins kept literally | not measured | 22 | 22 |
| Unlisted lead-in rejections | not measured | 100 | 100 |
| Lost verb-group words | 20 | 0 | 0 |
| Citation after subject dropped | 4 | 0 | 0 |
| Ownership: OWN | 73 | 126 | 134 |
| Ownership: PRIOR | 2 | 2 | 2 |
| Ownership: UNCLEAR | 310 | 118 | 110 |
| Epistemic strength: None | 187 | 115 | 190 |
| Epistemic strength: high | 147 | 99 | 28 |
| Epistemic strength: moderate | 30 | 24 | 23 |
| Epistemic strength: absolute | 11 | 5 | 5 |
| Epistemic strength: low | 10 | 3 | 0 |
| Distinct normalized frames | 83 | 67 | 70 |
| Distinct cluster keys | 346 | 208 | 207 |

After phase 7, the 246 extracted items have epistemic statuses: assigned 56, neutral 133,
ambiguous 0, unknown 57. Assigned strengths by reporting form were demonstrate 16,
demonstrates 7, demonstrated 1, confirm 3, confirmed 1, indicate 9, indicates 4, suggest 7,
suggests 3, and prove 5. No extracted `establish` form occurred. The 57 unknown statuses
include reporting forms outside the reviewed strength and neutral lists.

Before phase 7, all 15 `this`/`these` cases were UNCLEAR under the phase 6 contextual rule.
After phase 7, 8 are OWN and 7 are UNCLEAR. Tier B pairs counted as OWN: `these results` 5,
`these findings` 1, `this result` 1, and `this approach` 1. The two INTRO cases for `these
results` remain UNCLEAR under the section guard. By section, INTRO has 0 OWN / 3 UNCLEAR;
RESULTS 4 / 3; ABSTRACT 1 / 0; missing section 2 / 1; CONCLUSION 1 / 0. The five unlisted
pairs remain UNCLEAR:
`these methods`, `this gap`, `this robustness`, `these values`, and `this formulation`.
The missing previous-sentence cases are not blockers.

After phase 7, subject counts include `we` OWN 71, `our` OWN 13, citation-subject PRIOR 1,
and `this`/`these` OWN 8 / UNCLEAR 7. All reporting outputs have no lost verb-group words,
no dropped subject citations and no dropped accepted lead-ins. Rejection reasons include
unlisted_lead_in 100, unlisted_modifier 17, unmatched_content 27, empty_noun_phrase 18,
and subject_too_long 8.

Unapproved lead-in candidates observed (counts only): then 2, empirically 2, in this section
2, from the figure 2, together 2, in fact 2, additionally 2; 30 free-text lead-ins longer
than four words. Singletons (count 1 each): from which, in section, in our experience, next,
based on the results, on the attack end, from our observation, for simplicity, for model
performance, between fedtree and crypten, as shown in figure, in the experiment, here, in
figure for instance, through microbenchmarks, regarding march, besides the model architecture,
given this in practice, bias, convergence time, from the results, and for example. They remain
only in the backlog for owner review.

The previous phase 6 analysis reported 73 `None` strengths: 68 with no marker anywhere
(observe 21, assume 14, find/found 13, note 7, reveal(s) 3, conclude 4, imply(s) 3, argue
2) and 5 with multiple classes; four of 130 assigned strengths came from words outside the
reporting verb. Phase 7 counts are frame-only and therefore are not directly comparable at
the marker-cause level. Current accepted unknown outputs include reveal 1, reveals 3, imply
1, implies 2, conclude 2, concludes 1, concluded 1, and argue 2. Additional unlisted verbs
remain unknown; the syntax-analysis `no_that` rejection counts include report 60, state 1,
claim 1, verify 8, highlight 25, propose 174, reveal 9, imply 7, and conclude 14. Those
rejected items were not tagged and are separate from the 57 unknown statuses. No markers
were added for these verbs.

## Test expectation changes

- The mining registry order test now expects extraction before epistemic tagging because the
  tagger must inspect the masked reporting frame.
- The prior contextual-determiner test now asserts Tier B OWN in RESULTS without requiring an
  own-study cue; the former cue list has been removed.
- The `These findings` negation/frame expectation now uses a separate determiner slot because
  its listed Tier B pair is eligible in RESULTS.
- Invalid-token regex fallback and stored-token syntax tests use the same Tier B slot split;
  their clause span is now Z rather than Y.
- The phase 4 reporting-precedence test expects the same Tier B determiner+noun slot shape;
  reporting extraction still wins over construction matching.
- The phase 3 parity allow-list remains explicit: dependency slot spans/citation boundaries,
  syntax-only dependency matches, and the closed `widely` modifier rejection each have a
  one-line reason in the test.
- V02 behavior is unchanged from before phase 7: `show/shows/showed/shown` still count as
  `high` for the writer-facing validator. The lexicon now has `validator_only_markers`
  (V02) and `mining_only_markers` (EpistemicTagger) next to the shared `markers`, so a mining
  lexicon edit cannot silently change V02. A pinned test snapshots V02's effective list.
- The integration policy-version assertion expects epistemic markers v0.3.0.
- The gold guideline v2 bump and its status notes were deliberately NOT committed; the
  committed guideline stays v1 and its marker table is stale until gold work resumes.
- The 51-article figures in this report were produced by Codex and have not been
  independently re-run; do not cite them as a re-benchmark.

## Unknowns and owner review

- The `show` conflict is resolved: it is neutral with no strength.
- `reveal`, `imply`, `conclude`, `argue`, `report`, `state`, `claim`, `verify`, `highlight`,
  and `propose` remain unknown until approved. Counts above are limited to extracted cases.
- `assume` is neutral for now. It is an assumption rather than evidence reporting and remains
  a candidate to leave the reporting class later.
- All ownership tier lists and the neutral verb list carry `TODO(owner, FR-06.2)` and need
  owner review.
- `show`/`shows` frame merging, persistence of modality/status, and all other listed
  out-of-scope work remain untouched.

## Verification

- `ruff check --no-cache src tests`: passed.
- `ruff format --check --no-cache src tests`: passed, 287 files already formatted.
- `mypy --cache-dir D:\\6_OJT\\Academic-Phrase-Rhetorical-Knowledge-Base\\tmp\\phase7-mypy-cache src/aprkb`:
  passed, 201 source files.
- `pytest tests/unit -q -p no:cacheprovider --basetemp=../../tmp/phase7-unit-final2` with
  `NLP_ENGINE=regex`: 552 passed, 1 skipped.
- Focused ownership/epistemic regressions: 46 passed.
- `pytest tests/integration -q -p no:cacheprovider --basetemp=../../tmp/phase7-integration-regex-rerun`
  with `NLP_ENGINE=regex` and both database URLs set from `.env.example` to
  `localhost:55433/aprkb_test`: 79 passed.
- `pytest tests/integration -q -p no:cacheprovider --basetemp=../../tmp/phase7-integration-spacy`
  with `NLP_ENGINE=spacy`, the same dedicated DB/port and the phase 3 venv: 79 passed.
- Snapshot generation used `scripts/generate_nlp_token_snapshots.py` with the phase 3 venv
  and `PYTHONPATH=src`; the final 83 prior cases are byte-identical, 2 cases were added,
  and the phase 6 snapshot prefix remains unchanged.
- Corpus counts were generated with `corpus.py`, `own_epi.py` (status/section tally added in
  a temporary worktree wrapper), and `leads.py`, each given the authorized blob root and
  `allowed.json`. Frame samples were suppressed; only counters are included here.

The phase 6 report is [here](261105-spacy-phase6-report.md).
