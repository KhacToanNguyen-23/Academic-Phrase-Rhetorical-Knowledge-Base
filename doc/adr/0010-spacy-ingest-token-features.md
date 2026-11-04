# ADR-0010: Rule-first ingest boundaries and stored token features

Status: Accepted by owner on 2026-11-04 for phase 2 (`FR-06.2`, `FR-07`).

## Context

The NLP spike compared the existing regex splitter with `en_core_web_sm`. The model is useful
for token attributes and dependency parsing, but a parser-only sentence boundary is not reliable
for scholarly punctuation: abbreviations, numeric headings and citation brackets need deterministic
character rules. The phase-2 gold set on real papers is still deferred.

## Decisions

1. **Option A:** run NLP once during ingest. Persist compact token features with each sentence;
   mining receives those features as data and does not import or run spaCy.
2. **Model:** use `en_core_web_sm` through `NLP_MODEL`. `NLP_ENGINE=regex` remains the default
   so the normal development and test setup has no spaCy dependency. `NLP_ENGINE=spacy` fails the
   ingest job clearly when spaCy or its model is unavailable; it never falls back silently.
3. **Rule-first boundaries:** character-level `boundary_candidates` is the only source of
   possible sentence starts. Rules classify a candidate as `SPLIT`, `NO_SPLIT`, or `UNSURE`.
   Regex resolves `UNSURE` with its existing heuristics. spaCy receives `True`, `False`, or
   `None` only at candidate offsets, so parser output cannot create a boundary before a citation
   such as `[12]`.

The shared vocabulary is in versioned `policies/sentence_rules.yaml`; abbreviations remain in the
versioned abbreviation policy. Each stored sentence records `boundary_source` as `rule:<id>` or
`parser`, and each article records the engine/model/policy metadata in `nlp_engine`. The first
sentence of each non-empty section is always `rule:start`; it is not counted as a parser decision.

This changes the default regex behavior: the pre-phase-2 fixture score was 16/24 and the new
rule-first resolver scores 24/24. That is a fixture-driven improvement, not a general quality
claim. New ingests use the new boundaries; previously ingested articles retain their old sentence
rows and boundary sources until re-ingest.

## Storage and safety

`sentences.nlp_features` is nullable JSONB containing schema-versioned token arrays. Token text is
never duplicated: offsets recover it from `sentences.text`. `articles.nlp_engine` is nullable for
legacy rows and records the last ingest configuration. Rights are checked before the blob is read
or parsed, and source text, token text and lemmas are not logged or written to audit snapshots.

If trimming removes a whitespace head or no parser ROOT survives, the feature JSON carries
`repaired: true`; this condition is counted and must be reviewed before phase-3 syntax consumers
trust ROOT.

The current migration graph has one head, `0008_merge_heads`; phase 2 adds
`0009_nlp_ingest_features`. The vocabulary branch's future `0009_merge_vocabulary` will require a
merge revision when the branches meet; it must not be silently rebased over this revision.

## Deferred

Phase 3 may let `SentenceFilter` and `SlotAbstractor` consume features for finite-verb checks,
auxiliary-chain tense and a `that`-clause fallback. NER, embeddings, LLMs and quality claims on
real articles remain out of scope. `NLP_ENGINE=regex` remains a supported compatibility path.

See [the round-1 spike report](../../plans/reports/261104-spacy-nlp-spike-report.md),
[the round-2 report](../../plans/reports/261104-spacy-nlp-spike-round2-report.md),
[the phase-2 implementation report](../../plans/reports/261104-spacy-phase2-report.md), and
[the phase-2 plan](../../plans/spacy-nlp-spike/phase-2.md).
