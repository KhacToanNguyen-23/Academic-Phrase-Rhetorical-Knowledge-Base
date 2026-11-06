# Mining scope

Implement rule-based sentence extraction in the worker with pending candidates, source provenance and two-round review. `NLP_ENGINE=regex` remains the default; `NLP_ENGINE=spacy` runs the rule-first boundary resolver and stores token features at ingest. Syntax reporting frames use the ROOT and its literal verb group, retain only the seven owner-approved lead-ins, and reject unexplained content with reason counts. Unlisted verb-group adverbs are rejected; citations directly following a subject or clause stay in that slot. Tense and modality are separate, and modality is not persisted yet. Ownership follows the versioned determiner+noun tiers: unconditional own, guarded own, prior, and unclear with a literal determiner. Tier lists are provisional (`TODO(owner, FR-06.2)`). Only reporting-path misses are offered to the versioned, closed-world construction registry. Mining stays spaCy-free and checks mining rights before source access. The policy-gated imperative branch and construction coverage remain provisional pending reviewed real-article samples. See [ADR-0007](../../../../../../doc/adr/0007-rule-based-slot-abstraction.md), [ADR-0010](../../../../../../doc/adr/0010-spacy-ingest-token-features.md), [ADR-0011](../../../../../../doc/adr/0011-construction-registry-and-frame-statistics.md), and [ADR-0012](../../../../../../doc/adr/0012-slot-abstractor-frames-and-ownership.md).

The `extraction` module (`/extract` page) queues this mining per import batch and lets one reviewer accept phrases into `approved_phrases`; see [ADR-0009](../../../../../../doc/adr/0009-phrase-extraction-page.md).

Ownership uses four determiner+noun tiers in `slot_abstraction.yaml`: unconditional own, context-guarded own, prior, and literal unclear. The phase 6 own-study cue list has been removed. Epistemic tagging runs after extraction on masked frames; `show` and the reviewed neutral verbs leave strength unset and carry an in-memory epistemic status. Status is not persisted or included in `cluster_key`. These tier and neutral-verb lists remain provisional (`TODO(owner, FR-06.2)`).

The spaCy shared-token-feature spike is recorded in [the round-1 report](../../../../../../plans/reports/261104-spacy-nlp-spike-report.md), [the round-2 report](../../../../../../plans/reports/261104-spacy-nlp-spike-round2-report.md), [the phase-2 report](../../../../../../plans/reports/261104-spacy-phase2-report.md), [the phase-3 report](../../../../../../plans/reports/261104-spacy-phase3-report.md), [the phase-6 report](../../../../../../plans/reports/261105-spacy-phase6-report.md), and [the phase-7 report](../../../../../../plans/reports/261105-spacy-phase7-report.md).

`make phrase-stats ARGS="--focal-batch <uuid> --background all-other"` reports document frequency for masked candidate frames. It excludes rejected candidates, counts each candidate once per article, and never reads or prints sentence text. Results are descriptive; when the focal set is small or the background is empty, only the recurrence ranking is shown. `python apps/backend/scripts/mining_trial_report.py <directory> --blob-root <blob-root>` runs the local aggregate-only spaCy trial. Before opening file contents, it verifies every relative blob key against an article whose license metadata allows mining. Optional Windows-only `--dump <path>` writes imperative and coordinated sentences for manual review to a new ignored file directly under `tmp/`; stdout and the committed report remain counts-only.


Phase 8 adds a closed, versioned adjunct inventory to `author_action`: allowed prepositions
remain literal and their objects become slots; purpose `advcl`/`xcomp` clauses require a `to`
marker. Frames replace only the selected source spans, preserve the rest of the sentence, and
marker. Phase 8.1 corrected object-internal PP handling: those PPs remain inside the direct
object slot, and only predicate-level PPs are checked against the closed adjunct list. Unsupported
predicate adjuncts reject as `unsupported_adjunct`; more than two adjunct slots reject as
`too_many_adjuncts`. Candidate discourse modifiers and auxiliaries are held in the separate
`construction_verb_groups.yaml` policy and require matching dependency, POS and surface position.
Phase 9.1 adds only active literal subjects `this paper`, `this study`, and `this article`; other
subject phrases reject as `unsupported_subject`, and passive subjects reject as
`unsupported_voice`. Phase 8.1 does not add anchors, adjuncts or subjects. Provisional anchor,
adjunct, modifier and auxiliary lists carry `TODO(owner, FR-06.2)`; see
[ADR-0013](../../../../../../doc/adr/0013-author-action-adjuncts.md) and the
[Phase 8.1 report](../../../../../../plans/reports/261106-spacy-phase8.1-report.md).

ADR-0014 adds an open-world, eight-family Tier 2 fallback in `hybrid_constructions.yaml`. Tier 1
remains authoritative; fallback runs only after reporting and construction misses, when
`MINING_HYBRID_ENABLED=true` and stored usable spaCy tokens exist. Mining does not load spaCy.
The switch defaults off, and regex-ingested articles remain Tier 1-only. Hybrid frames use the
same pending-candidate review flow and must pass family identity, Frame Invariant, Purity Gate,
and existing review checks.

## One candidate per cluster

`candidates.cluster_key` is unique. The worker upserts each draft and appends its source sentence
and occurrence to the existing candidate, in sorted key order, without changing the review status.
Run migration `0012_candidate_cluster_unique` before starting the worker. Sources and rights are
read through `sentences`, so a promotion checks the current licence of every source.

Slot text is not part of `cluster_key`, so one frame with the same tense, strength, ownership and
slot types is one candidate. Tier 1 reporting keys use the reporting verb class from the lexicon.
