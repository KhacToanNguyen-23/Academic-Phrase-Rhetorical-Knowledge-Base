# Plan: IMRaD section label for mined frames (first frame label)

Status: phase 1b/phase 2 section-label work implemented and measured for owner review, 2026-11-08. Frame labels now distinguish observed source distribution (`observed_sections`) from AI-proposed allowed scope (`section_scope`), with proposal/approval persisted separately in `candidate_labels` (`FR-01`, `FR-02`). AI review is an explicit, rights-gated worker job, not part of extraction or recommendation request paths. No 50-article database label run was possible because `TEST_DATABASE_URL` is unset; validation uses synthetic candidates and a fake provider. Vocabulary, provider activation, and review ordering remain provisional (`TODO(owner, FR-01)`). Worktree `D:\6_OJT\aprkb-spacy-spike`, branch `feat/spacy-nlp-spike`.

Phase 1b adds formal-block exclusion and reporting-only inferred METHODS labels. See
`tmp/work/imrad-phase1b-report.md` for the before/after UNKNOWN, inference, formal-block, and
hybrid mining coverage measurements. Definition/Assumption inheritance is configurable; the
default is `exclude` because only three METHODS candidate sentences were found, none passed the
mining filter, and no frames were extracted.

## Goal

Every mined frame carries a trustworthy IMRaD label (ABSTRACT, INTRO, RELATED_WORK, METHODS, RESULTS, DISCUSSION,
CONCLUSION, or UNKNOWN) derived from the sections of its source sentences. The label must be measurable against a
gold set, and the section label itself must be correct before it is used on frames.

## Why now (measured on 50 FL articles, policy v0.9.1)

- 40% of sentences reaching the engine are UNKNOWN; only 9/50 articles get METHODS and 7/50 DISCUSSION.
- Bug: `SectionDetector._is_top_heading` accepts an arabic top number only if it equals the last number or last+1.
  When the export drops a top heading (only `2.1`, `2.2`, or a bare `### 2.`), every later top heading is rejected
  and inherits the previous code. 17/50 articles have 46 rejected top headings; Methods, Experiments, Discussion and
  Conclusion get labelled INTRO until the end of the article.
- An unmatched top heading yields `None`, and all its sub-headings inherit `None` (UNKNOWN). 115 top headings are
  unmatched (for example `System Design`, `Algorithm design`, `<Tool> Overview`).
- Section labels already drive mining behaviour, not only reporting: `sentence_filter` excludes sections, and
  `slot_abstractor._ownership_decision` blocks own-work ownership in INTRO/RELATED_WORK. A wrong INTRO label changes
  extracted frames.
- Compound headings (`Results and Discussion`, `Conclusion and Future Work`) can carry only one code.
- Some articles have no Discussion section at all (24/50 have no discussion-like heading). That is real, not a bug;
  the target is correct labels, not a quota per section.

Evidence: `tmp/work/section-survey-report.md`, `tmp/work/why_sections.py`, `tmp/work/why_seq.py`.

## Design

### Phase 1 - section detection algorithm (corpus module)

1. Numbering-sequence repair (`section_detector.py`).
   - Accept an arabic top heading when its number is greater than the last accepted top number by at most a small
     gap (policy value `max_top_number_gap`, provisional 3, `TODO(owner)`), not only +1.
   - A sub-heading `N.k` whose parent `N` was never seen opens an implicit top section `N`: its code comes from the
     sub-heading's own match, else UNKNOWN. It never inherits the previous top section's code.
   - Keep the guard against list items and algorithm lines promoted to headings: reject a candidate top heading when
     the number decreases, jumps more than the gap, or the heading looks like a sentence or code line (length, ending
     punctuation, keywords such as `return`, `if ... then`). Thresholds go in YAML with `TODO(owner)`.
2. Heading vocabulary (`policies/section_headings.yaml`, bump version).
   - Add narrow patterns measured in the survey: METHODS (`system design`, `architecture`, `algorithm(s)? design`,
     `design of`, `model design`, `threat model`, `framework design`), RESULTS (`benchmark`, `ablation`,
     `experimental (results|analysis)`, `case stud`), CONCLUSION (`conclusion and future work`, `future work`),
     DISCUSSION (`lessons learned`, `threats to validity`). Every new list is `TODO(owner, FR-07)`.
   - Do not add broad secondary words (`overview`, `framework` alone) or position-only rules: the survey showed
     mislabels (`Theorem 2.`, `FL FRAMEWORK COMPARISON`).
3. Compound headings.
   - Detect `X and Y` headings where both parts match different codes. Primary code = first part (keeps one code per
     sentence, no schema change); record the secondary code in a new nullable field on the detector output
     (`secondary_code`) for later use. Persisting it is phase 2 (needs a migration; owner decides).
4. Label provenance.
   - Detector returns, per section, `code` and `source` in {`heading`, `inherited`, `implicit_parent`, `none`}.
     Keep `detect()` backward compatible (codes list); add `detect_with_provenance()`.
5. Gold set and evaluation (`eval/sections/`).
   - Gold = for each of the 50 articles, the list of headings (heading text only, no body text) with the expected code.
     AI pre-labels, one human approves before use (same rule as the mining gold). Store as YAML/JSON under
     `eval/sections/gold/`, git-ignored if the owner considers heading text copyrighted (`TODO(owner)`).
   - Script `apps/backend/scripts/section_label_report.py`: sentence-weighted and heading-weighted accuracy per code,
     confusion matrix, UNKNOWN share, count of articles with INTRO bleed (INTRO after a later top heading), articles
     per code. Rights check before reading blobs. Counts only.
   - Acceptance (provisional, `TODO(owner)`): 0 articles with INTRO bleed; sentence-weighted accuracy >= 90% on the
     approved gold; UNKNOWN share reported, not a hard target.
6. Tests: unit tests with self-authored synthetic heading sequences only (missing top heading, bare `### 2.`,
   algorithm lines, compound headings, unnumbered documents, roman numerals, appendix letters). No article text.

### Phase 2 - frame IMRaD label (after owner reviews phase 1 numbers)

- A frame (mining candidate, one per cluster) gets a section distribution from its source sentences
  (`article_sentences.article_section_id -> article_sections.section_code`): counts per code, dominant code, and
  share. Dominant code is the frame's IMRaD label; ties or share below a policy threshold -> `MIXED`
  (`TODO(owner)`).
- Read-side first (API/service computes it from sources); persist only if needed for filtering performance.
- Re-ingest or re-detect existing articles: provide a one-shot command that recomputes `article_sections.section_code`
  with the new detector (dry-run mode prints counts of changed labels).
- Rerun the 50-article report and the PDF v3 with the corrected per-section table.

### Out of scope

Rhetorical target labels (aim, finding, ...), position labels, multi-discipline tuning, frontend changes.

## Risks

- Changing section codes changes ownership decisions and extracted frames: measure before/after with
  `scripts/mining_coverage_report.py` on the same 50 articles and report the delta.
- Heading text in the gold set may be copyrighted: keep it out of git until the owner decides.
- 50 articles from one field: patterns may overfit; keep them narrow and flagged.

## Status update (2026-11-08)

- Phase 2 section distribution and read-side UNKNOWN single-paper policy are implemented; the
  optional sandwich assignment remains measurement-only and OFF by default.
- `long_methods_parent_override` now applies the four narrow METHODS phrase patterns under a
  rhetorical parent and scopes each override to its numbered subtree. Exclusion regions remain
  authoritative (`TODO(owner, FR-07)`).
- A no-migration `FrameLabels` read record and four owner-approved proposal-only anchor families
  are exposed in `/extraction/phrases` (`TODO(owner, FR-01)` / `TODO(owner, FR-02)`). No import
  adapter, confirmed labels, or group-3 classifiers are active (`TODO(owner, FR-01)`).
- Epistemic strength is measured with the existing tagger only; its marker inventory and negation
  behavior still need owner review (`TODO(owner, FR-06)`).
