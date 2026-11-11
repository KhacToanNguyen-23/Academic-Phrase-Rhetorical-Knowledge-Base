# Mining scope

Implement rule-based sentence extraction in the worker with pending candidates, source provenance and two-round review. `NLP_ENGINE=regex` remains the default; `NLP_ENGINE=spacy` runs the rule-first boundary resolver and stores token features at ingest. Syntax reporting frames use the ROOT and its literal verb group, retain only the seven owner-approved lead-ins, and reject unexplained content with reason counts. Unlisted verb-group adverbs are rejected; citations directly following a subject or clause stay in that slot. Tense and modality are separate, and modality is not persisted yet. Ownership follows the versioned determiner+noun tiers: unconditional own, guarded own, prior, and unclear with a literal determiner. Tier lists are provisional (`TODO(owner, FR-06.2)`). Only reporting-path misses are offered to the versioned, closed-world construction registry. The worker keeps rule-based mining available without spaCy and checks mining rights before source access. The policy-gated imperative branch and construction coverage remain provisional pending reviewed real-article samples. See [ADR-0007](../../../../../../doc/adr/0007-rule-based-slot-abstraction.md), [ADR-0010](../../../../../../doc/adr/0010-spacy-ingest-token-features.md), [ADR-0011](../../../../../../doc/adr/0011-construction-registry-and-frame-statistics.md), and [ADR-0012](../../../../../../doc/adr/0012-slot-abstractor-frames-and-ownership.md).

The `extraction` module (`/extract` page) queues this mining per import batch and lets one reviewer accept phrases into `approved_phrases`; see [ADR-0009](../../../../../../doc/adr/0009-phrase-extraction-page.md).

The phrase-list read path aggregates each candidate's source article IDs and section codes,
exposes its IMRaD distribution, and applies `unknown_single_paper_reason()` under policy
`mining_filter.unknown_single_paper_filter`. A frame is UNKNOWN when none of its source section
codes is one of the seven rhetorical IMRaD codes; non-rhetorical and missing codes do not count
as known. `PhrasePage.filtered_reason_counts` exposes only audit reason counts. The filter changes
the read response and pagination, not extraction or stored candidates. The policy also sets the
minimum dominant share required to report one dominant section code; ties or a share below that
threshold are labeled `MIXED`.

Ownership uses four determiner+noun tiers in `slot_abstraction.yaml`: unconditional own, context-guarded own, prior, and literal unclear. The phase 6 own-study cue list has been removed. Install the optional `nlp` extra with `uv sync --extra nlp` to provide spaCy and the pinned `en_core_web_sm` model in the worker environment. For a Docker image, pass `--build-arg INSTALL_NLP=true`; the default image stays lean and uses the fallback. The worker loads that model and the dependency-based scorer once at boot. Ingest and mining are separate queue jobs, so the mining job reparses each sentence and scores the spaCy `Doc` immediately before constructing its `MiningItem`; the `Doc` is not persisted. API and worker processes do not share an in-memory model. If spaCy or its model cannot load, mining continues with `epistemic_strength=None`, `epistemic_score=None`, and provenance `unscored_no_spacy_doc`. The scorer combines the assertion predicate's lexical baseline with modal auxiliaries, adverbial modifiers, selected evidence/doubt phrases, and explicit refutation. Results include a continuous score and one of four strength tiers; explicit refutation is reported separately as `negative_refuted`. A possibility modal caps the score at `0.8` and forces the `low` tier. Candidate rows continue to store the tier only; score and provenance remain on the in-memory `MiningItem`. Lexical classes and weights are provisional (`TODO(owner, FR-06.2)`).

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
and existing review checks. Policy v0.8.0 keeps the configured fixed lead-ins literal, rejects
modifier/head splits and capitalized sentence joins after a slot, and requires two fixed content
tokens. That threshold is provisional (`TODO(owner, FR-06.2)`) pending review of a fresh corpus
sample.

## One candidate per cluster

`candidates.cluster_key` is unique. The worker upserts each draft and appends its source sentence
and occurrence to the existing candidate, in sorted key order, without changing the review status.
Run migration `0012_candidate_cluster_unique` before starting the worker. Sources and rights are
read through `sentences`, so a promotion checks the current licence of every source.

Slot text is not part of `cluster_key`, so one frame with the same tense, strength, ownership and
slot types is one candidate. Tier 1 reporting keys use the reporting verb class from the lexicon.

## Frame labels and AI-assisted review

`/v1/admin/extraction/phrases` preserves the existing `section_distribution` field and exposes a
status-tagged `labels` record. `observed_sections` is derived from source headings; `section_scope`
is a proposed set of allowed sections and is never inferred from the observed distribution.
`article_genres` is a list from article metadata, and mined frames have derived
`source_class=corpus-inferred`. `sequence_hint` and human-only `constraints` remain unassigned
(`TODO(owner, FR-01)`). Pattern lifecycle status/version remains in the pattern tables.

| Frame label | Design-document field | Producer / status |
|---|---|---|
| `provenance` | `provenance_refs` | Candidate source counts and extraction metadata / derived |
| `license_status` | `license_status` | Current source rights, worst-case / derived |
| `slots` | `slots_schema` | Existing candidate slots / derived |
| `epistemic_strength` | `epistemic_strength` | Compositional scorer when a parsed spaCy sentence is supplied / derived |
| `article_genres` | `article_genres` | Source article metadata / derived |
| `observed_sections` | Observed source sections | `frame_sections` distribution / derived |
| `source_class` | `source_class` | Mining origin `corpus-inferred` / derived |
| `section_scope` | `section_scope` | AI proposal then human approval / proposed or confirmed |
| `function_group`, `intent`, `move`, `step` | `function_group`, `intent_id`, `Move`, `Step` | Two-pass AI proposal then approval |
| `claim_type`, `register`, `general_function` | `claim_type`, `register`, general function | Two-pass AI proposal then approval |
| `sequence_hint` | `sequence_hint` | Not proposed (`TODO(owner, FR-01)`) |
| `constraints` | `constraints` | Human-only; no AI guess (`TODO(owner, FR-01)`) |

The versioned `frame_label_vocabulary.yaml` is a provisional, self-authored closed vocabulary with
seven groups, a parent hierarchy, and explicit `unclear`/`none_of_these` choices
(`TODO(owner, FR-01)`). Four approved anchor families map into that vocabulary and remain
proposal-only (`TODO(owner, FR-02)`).

The PostgreSQL worker's `label_frames` job sends only a slot-abstracted frame, tier/construction
family, epistemic strength, paper count, observed section counts, and an anchor proposal. It first
checks mining and display rights for every source article. No sentence text is sent to a provider.
The job runs independent prompt variants `a` and `b`; agreement measures stability, not correctness,
because there is no gold set. `NullFrameLabeler` is the default. Groq requires
`FRAME_LABELER=groq`, local/test environment, `GROQ_ALLOW_EXTERNAL_PROCESSING=true`, and the local
key; no real provider call was made for this implementation. `TODO(owner, FR-01)` remains before
any externally processed data.

Curators queue the job with `POST /v1/admin/mining/frames/label`. Reviewers use
`GET /v1/admin/mining/frames` (label, confidence, attention, agreement, paper-count filters) and
`POST /v1/admin/mining/frames/decisions` (approve, edit, reject). The service locks candidates and
labels, validates values against the YAML vocabulary, and writes one audit entry per bulk request
containing label values/codes only. Confirmed labels include reviewer and UTC timestamp. New AI
runs do not overwrite confirmed or rejected rows. Only `derived` and `confirmed` values can be
used by recommendation; proposals and rejected labels are excluded.

`scripts/export_frame_label_review.py` writes `tmp/shared-frames-curation.xlsx`; source examples
are blank by default and can only be included by the explicit `--with-examples` option after
rights checks. The workbook is local-only and git-ignored. `scripts/frame_labels_apply_review.py`
applies workbook decisions through the same service with `--reviewer-id` and supports `--dry-run`.
Imports create no pattern rows and do not change pattern lifecycle status/version. Workbook
ordering prioritizes `needs_attention`; confirmation of final curation ordering remains
`TODO(owner, FR-01)`.

## Epistemic OOV lexicon

The mining scorer gates applicability from `ccomp`, `xcomp`, and configured relational objects.
Eligible unknown predicates receive the moderate fallback while a metadata-only enrichment job is
pending. The job payload contains only lexicon entry IDs; the Groq request contains lemma, POS,
construction family, and the closed strength vocabulary, never the source sentence.

External assessment is disabled by default. It also requires the source license's explicit
`allows_external_processing` policy flag; `allows_display` is not sufficient. Enable
`EPISTEMIC_LABELER=groq`, `GROQ_ALLOW_EXTERNAL_PROCESSING=true`, and `GROQ_API_KEY` only in
local/test after policy review.
Each batch is assessed in two separate model passes. Entries activate automatically only when both
passes return the same tier and each confidence is at least the configured 0.90 threshold. Low
confidence or disagreement becomes `needs_review`; a locked neutral-policy match becomes
`policy_conflict_hold`. Confidence is model-reported and is not a calibrated probability.

Reviewers can list entries at `GET /v1/admin/mining/epistemic-lexicon`; curators can activate,
reject, or deactivate revisions with `POST /v1/admin/mining/epistemic-lexicon/{entry_id}/review`.
`GET /v1/admin/mining/epistemic-lexicon/{entry_id}/audit` returns the append-only decision history.
Each mining job loads an immutable active-entry snapshot; later revisions affect later jobs only.
