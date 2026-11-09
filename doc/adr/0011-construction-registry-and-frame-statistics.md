# ADR-0011: Closed-world construction registry and frame statistics

- Status: accepted by owner for phase 4–5 implementation; values remain provisional.
- Date: 2026-11-04
- Requirements: FR-06.2, FR-07.

## Context

The reporting-verb extractor covers only one frame family. The next increment needs a small set of
self-authored discourse functional blocks and a way to find masked frames that recur in a journal
batch. Mining must continue to work without spaCy installed, and generic academic frames must not
rank highly just because they appear often across unrelated sources.

## Decisions

1. Add three initial construction groups: author action, relation/role, and performance/evaluation.
   Patterns are versioned in `policies/constructions.yaml`, depend on stored token features, and use
   a closed-world rule: every non-slot word must be a matched literal or an explicitly allowed token.
   This is an initial, non-exhaustive set. Extend it only with self-authored examples.
2. Run the existing reporting-verb path first. Offer only its misses to the registry. Existing
   reporting output, regex behavior, and sentence-level cluster keys remain unchanged. Construction
   cluster keys carry the construction id and registry version.
3. Do not import spaCy under mining. Normalize only direct `mark`/subject dependents attached to
   one auxiliary level when that auxiliary belongs to a clause head. Relative-clause markers remain
   out of the reporting clause.
4. Allow bare imperative roots only under a policy flag and only with a direct complement, no
   grammatical subject, and a sentence-initial position (or one short adverb/discourse token plus a
   comma). Counts do not contain text. Keep `TODO(owner, FR-07)` until a reviewed manual sample
   estimates false positives.
5. Do not change modal tense or epistemic-strength behavior in this phase. Modal strength can remain
   `None` when multiple classes match; modal + `have` + participle continues to use the current
   baseline tense rule with `TODO(owner, FR-06.2)`.
6. Phrase statistics count each frame at most once per article for document frequency. Use a frame
   key separate from `candidates.cluster_key`; preserve verb forms and tense. Contrast focal and
   background document frequencies with smoothed log ratio. This is descriptive, not significance
   testing. Exclude rejected candidates; pending and accepted count.
7. Provide a read-only CLI and service only. No endpoint, schema change, migration, change to mining
   candidate output, or article text in logs/output. If the focal set is below the warning threshold
   or the background is empty, show recurrence only and state why contrast is unavailable/unstable.

## Consequences and limits

- Construction rules and phrase-statistics thresholds are provisional, versioned YAML with
  `TODO(owner, FR-06.2)` markers.
- JATS/PDF parsing, NER, move classification, coordination support, sub-sentence collocations,
  section-level statistics, lemma/number merging, significance testing, and UI/API exposure remain
  deferred.
- Real-article trial counts describe only the supplied file set and its recorded license state.
  They do not establish construction quality or journal-specificity. Imperative false-positive review
  remains an owner task.
- Never commit the source articles or copy sentence/frame samples from them into tests or reports.
