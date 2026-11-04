# spaCy NLP — phase 3: SentenceFilter and SlotAbstractor consume stored token features

Status: implemented, pending owner review 2026-11-04; changes intentionally left uncommitted.
Requirement: `FR-06.2`, `FR-07`.
Branch/worktree: `feat/spacy-nlp-spike`, `D:\6_OJT\aprkb-spacy-spike` (phase 2 is commit `8548bf5`).
Read first: `plan.md`, `phase-2.md`, `doc/adr/0010-spacy-ingest-token-features.md`, the phase-1/2/3 reports.

## 1. Goal and principles

Phase 2 stores per-token features (`pos`, `tag`, `dep`, `head`, `lemma`, `morph`, offsets) with each
sentence and passes them to mining as `MiningItem.tokens`, unused. Phase 3 makes two stages read them:

1. `SentenceFilter` rejects fragments and headings using a finite-verb check.
2. `SlotAbstractor._locate` finds the reporting verb, subject and `that`-clause from the dependency
   tree instead of from "longest regex form / everything before the verb / everything after `that`".

Principles (owner decisions, do not relitigate):

- **Syntax is evidence, the lexicon stays the authority.** A verb counts as a reporting verb only if
  its lemma is in `policies/lexicon/reporting_verbs.yaml`. spaCy never invents a reporting class.
- **No tokens ⇒ no change.** With `NLP_ENGINE=regex` (default) every stage must behave byte-for-byte as
  today. The regex path is also the fallback when stored tokens are missing or invalid.
- **Only span-finding changes.** `_extract` (slot typing, frame string, occurrence offsets, binding
  fingerprint, ownership) is reused unchanged. The syntax path produces the same `_Located` object the
  regex path produces.
- **POS is not enough.** spaCy mis-tagged `noise` as VERB in `robust to noise`. Decisions use `dep`
  and the lexicon; POS is only a guard (for example "subject head is a noun/pronoun").
- No source text, token text or lemma in logs, audit or public outputs. Token text is recovered from
  `item.text` and offsets. No NER, no LLM, no new dependencies. Mining must not import spaCy.

## 2. Out of scope

- The sub-sentence collocation use case (`significantly improves [SLOT] accuracy`, `compound` vs
  `amod`). It needs an owner definition of "phrase" first; list it as an open question in the report.
- Move classifier, dedup matcher, synonym expansion, coordinated reporting verbs
  (`X shows and Y suggests that …`; reject with a counted reason, do not guess).
- Re-ingesting existing articles, UI, new endpoints, changes to pattern/version tables.

## 3. SentenceFilter with tokens

Add `SentenceFilter` rules that run only when `item.tokens` is present, after the existing checks:

| Reason | Condition |
|---|---|
| `no_finite_verb` | no token with `pos` in {VERB, AUX} whose `morph` has `VerbForm=Fin`, and no modal (`tag == "MD"`) |
| `root_not_verbal` | the ROOT token's `pos` is not VERB or AUX (headings, noun-phrase fragments, captions) |

- Ignore tokens with `is_space`. Put the on/off switch and any thresholds in
  `policies/mining_filter.yaml` (`syntax_filter: {require_finite_verb: true}`), version bump to
  `0.3.0`, `TODO(owner, FR-07)` on provisional values. `reject_reason` keeps returning a string reason
  so the evaluator statistics keep working.
- Before enabling by default, measure on the fixtures how many currently accepted sentences the new
  rules reject and list them in the report (imperatives and elliptical but useful sentences may be
  caught; if so, show examples and propose a rule, do not tune silently).

## 4. SlotAbstractor syntax locator

Add `_locate_syntax(item) -> str | _Located` next to `_locate`. `_locate` becomes:
use the syntax locator when `item.tokens` passes validation, otherwise the existing regex locator.

Validation (any failure ⇒ regex fallback and a counted reason `syntax_invalid_tokens`, no text logged):
offsets inside `item.text`, `start < end`, heads inside range, exactly one ROOT.

Algorithm:

1. ROOT = the single token with `dep == "ROOT"`. Its lemma (case-folded) must be in the reporting-verb
   lemmas; else `no_reporting_verb`. If a `conj` child of ROOT is also a reporting verb, return
   `coordinated_reporting_verbs`.
2. Reporting class and base tense come from the lexicon entry for that lemma.
3. Subject = subtree span of the `nsubj`/`nsubjpass` child of ROOT, trimmed (see
   `scripts/nlp_spike_compare.py` for the already fixed helper; move it into `aprkb/nlp/` so both use it).
   For `It is … argued that …` the subject is `It` (expletive/passive) and the clause is the
   `that`-clause. Missing subject ⇒ `no_subject`.
4. `that`-clause = the subtree of the direct child of ROOT that has a child with `dep == "mark"` and
   lemma `that`. Do **not** require `dep == "ccomp"`: in the phase-1 probe `These findings may indicate
   that the baseline was undertrained` had a clause without `mark=that` attached as `ccomp`, and other
   parses may label it differently. None found ⇒ `no_that`. A relative clause such as
   `a framework that unifies …` must **not** count (its `that` has `dep == "nsubj"`, not `mark`).
5. Verb group = the ROOT plus the contiguous `aux`, `auxpass`, `neg` and `advmod` tokens between the
   subject end and the ROOT. These stay literal in the frame exactly like the regex `modifiers`
   (`do not suggest` must never be masked). Unlisted adverbs also stay literal, which fixes the regex
   behaviour of absorbing them into the subject.
6. Tense from the verb group, not from the ROOT alone: aux `did` or finite past ⇒ PAST;
   `has/have` + participle ⇒ PRESENT_PERFECT; finite present ⇒ PRESENT; passive ⇒ tense of the finite
   aux; modal ⇒ the regex baseline (PRESENT for `may suggest`). Document modal handling as
   `TODO(owner, FR-06.2)`. Never infer tense from the ROOT `morph` alone (`VerbForm=Inf/Part` is
   common for ROOT in these sentences).
7. Reuse the existing guards: `max_subject_words`, `min_clause_words`, determiner detection,
   `empty_noun_phrase`.
8. Optional: if the subject head's `pos` is not NOUN/PROPN/PRON, return `subject_not_nominal` rather
   than guessing.

If the lexicon lists forms but not lemmas, add an explicit `lemmas` list per class in
`reporting_verbs.yaml` (version bump `0.3.0`, `TODO(owner, FR-06.2)`); do not derive lemmas from the
class key unless every class key equals its lemma.

`extractability_reason(text)` gains an optional `tokens` argument so the evaluator and the extraction
page statistics report syntax reasons too. Add the new reasons to the evaluator's reason set.

## 5. Cluster keys and provenance

- The cluster key must not change for items produced by the regex path.
- For items produced by the syntax path add `locator=syntax:<model_name>:<model_version>` to the key
  material (and nothing for regex). Reading the stored engine info from `articles.nlp_engine` is
  allowed; carry it on `MiningItem` as a small string field.
- Candidate records may store which locator produced them in an existing metadata/JSON field; if none
  exists, do not add a column in this phase, report it as an open item.

## 6. Tests (hand-built tokens, spaCy not required)

Most tests must run without spaCy:

- Generate once, from the committed spike environment, JSON snapshots of `SentenceAnalysis` for the 10
  `slot_cases` plus the new cases below, and commit them under
  `tests/fixtures/nlp_spike/token_snapshots.json` with the model name and version inside. A small
  generator script lives in `apps/backend/scripts/`. Tests load the snapshots and build
  `MiningItem(tokens=…)`.
- Add self-authored cases (no real article text): reporting verb with a parenthetical second verb
  (`We show that the gain, as Lee demonstrated, is stable.` must now be extracted with verb `show`),
  `clearly show`, `did not reveal`, `have reported`, passive `It is widely argued that`, modal
  `may indicate`, relative clause `a framework that unifies` (must stay `no_that`), coordinated verbs,
  an unlisted adverb between subject and verb, a heading and a fragment for the filter.
- **Parity test:** for every case in `test_slot_abstraction*.py` that the regex path extracts, run it
  with snapshot tokens and compare frame, slots, tense, ownership and spans. Differences must be
  enumerated in an allow-list in the test with a one-line reason each; any unlisted difference fails.
- Validation fallback: corrupt offsets, two ROOTs, empty tokens ⇒ identical output to the regex path.
- `tokens=None` ⇒ identical output to today for the full existing suite (no existing test edited
  except to add cases).
- Integration (PostgreSQL, `TEST_DATABASE_URL`): ingest with `NLP_ENGINE=spacy`, mine, assert the
  parenthetical case now produces a candidate, and `NLP_ENGINE=regex` output is unchanged.

## 7. Report and docs

- Update ADR-0010 (or add ADR-0011) with the locator design, the fallback rule, tense rules and the
  cluster-key rule. Update ADR-0007, `README.md`, `SCAFFOLD_PRD.md` and the mining README. Keep
  `TODO(owner, FR-06.2)` on every provisional list; do not claim quality on real data.
- Report `plans/reports/YYMMDD-spacy-phase3-report.md` with: the regex-vs-syntax comparison table over
  the fixtures (both extract and equal / both extract and differ / only regex / only syntax /
  neither), each difference explained; filter rejections added and examples; reason counts;
  integration results and the exact commands; environment commands (dedicated venv, versions);
  open items (collocation definition, modal tense, coordination, candidate locator metadata).
- The fixtures are self-authored and tuned with the rules, so state clearly that the comparison is a
  regression and design check, not a quality measurement. Quality evaluation belongs to the gold set
  on real articles.

## 8. Done when

- `make lint` and `make test` pass without spaCy; snapshot-based tests run without spaCy.
- spaCy-marked tests and PostgreSQL integration tests pass (regex and spacy modes); if PostgreSQL or
  spaCy is unavailable, list exactly what was not run.
- Parity test passes with a reviewed allow-list; regex-mode behaviour unchanged.
- Docs and report written; phase-3 changes left uncommitted for owner review.
