# Plan: Hybrid Slot Engine (Tier 2)

Status: ready for Codex. Owner decisions O1 and O2 are recorded below.
Requirement: `FR-06.2`. Spec: `plans/hybrid-slot-engine/spec.md`.
Worktree: `D:\6_OJT\aprkb-spacy-spike`. Branch: `feat/spacy-nlp-spike`. Base: `21299c4` (Phases 8, 8.1, 9.1).

**Do not implement on `feat/ui-redesign`.** The spec was drafted against that branch, which has none of the NLP work. Where this plan and the spec disagree, this plan wins (section 2).

## 1. Goal and working style

Raise coverage. The latest corpus run (Phase 8.1, 51 articles, one field) kept 12,178 sentences and extracted 363: 203 reporting and 160 construction, about 3%. `no_anchor` alone rejected 10,139.

The owner chose breadth first: build all seven families in one pass, run on the real corpus, then fix the most frequent errors. Do not stop for review after each family. Do not tune single sentences.

## 2. Spec corrections (this plan wins)

| Spec says | Actual state on the spike | Do this |
|---|---|---|
| `ConstructionMatcher` does not exist; `SlotAbstractor` coordinates | `ConstructionMatcher` and `ReportingWithConstruction` exist in `stages/construction_matcher.py` | Tier 1 = `SlotAbstractor` + `ConstructionMatcher`. Add the hybrid call in `ReportingWithConstruction`, not in `SlotAbstractor` |
| FR-03: add `Sentence.analysis`, `Article.analysis_info`, `MiningItem.analysis` | `sentences.nlp_features`, `articles.nlp_engine`, `MiningItem.tokens`, `usable_tokens()` exist (migration `0009_nlp_ingest_features`) | Reuse them. No storage migration |
| FR-04: new alignment checks | `validate_token_features(text, tokens)` exists | Reuse it |
| FR-07, rollout: extend `constructions.yaml` and `slot_abstraction.yaml` | `slot_abstraction.version` feeds `Clusterer._policy_version`; `constructions.version` feeds `construction_version` in the cluster key. Bumping either changes Tier 1 cluster keys | Do not edit either file. Put everything in a new `hybrid_constructions.yaml` |
| FR-09: modal maps to `UNKNOWN` | `SlotAbstractor._syntax_tense` maps modal to `PRESENT`/`PRESENT_PERFECT`; `ConstructionMatcher` reuses it | Reuse `_syntax_tense`, so tiers agree |
| FR-10: unfamiliar words are flagged on the candidate | With no word list there is nothing to compare against, and no field or UI for a flag | Drop the flag in this release |
| FR-13/FR-15: the protected gate is the 42 parameterized reporting tests | The Phase 8.1 gate is a different set: 42 `author_action` corpus instances in `261105-spacy-phase8-report.md`. It is unverified and Phase 8.1 is **not accepted** because the identity recipe is missing | Keep the 42 + 16 unit tests, and add the new baseline in Phase 1. See O2 |
| FR-16: scope exception and migration prerequisite | ADR-0011 permits only a *closed-world* registry; `CLAUDE.md` forbids general-purpose NLP extraction | Hybrid is open-world, so it needs a new ADR (Phase 6). `CLAUDE.md` is owner-owned: propose wording, do not edit |
| Status quo for review | Not in the spec | `review/service.py`, `review/router.py` and `extraction/service.py` re-check frames. Hybrid frames would fail with 409 or be hidden. Fix in Phase 2 |

## 3. Owner decisions (2026-11-06)

- **O1. Done.** Phases 8, 8.1 and 9.1 are committed as `21299c4`, so the hybrid diff stays separate. Phase 8.1 is still "not accepted". Left uncommitted on purpose: `gold_labeling.yaml`, `eval/mining/gold/*`, and `plans/spacy-nlp-spike/verb-queue-spec.md`.
- **O2. Decided.** `21299c4` is the Tier 1 reference, and Phase 1 creates a new reproducible baseline. The old 42 hashes stay an open Phase 8.1 acceptance item, because they cannot be joined without the lost recipe.

## 4. Hard constraints

- Do not change behavior in `slot_abstractor.py` or the matching logic of `construction_matcher.py`. Do not edit `constructions.yaml`, `slot_abstraction.yaml`, `construction_verb_groups.yaml`, `lead_ins`, or reporting verbs.
- A Tier 1 result is final. Tier 2 runs only when both Tier 1 matchers miss, the switch is on, and `item.tokens` is usable.
- Mining never loads spaCy.
- No Tier 3, no shadow mode, no academic word list, no move classification, no auto-approval, no new `SlotType`, at most slots `X`, `Y`, `Z`.
- No source sentences or frames derived from real articles in logs, reports, fixtures, or commits. Reports use counts and hashes. Fixtures are self-authored.
- Integration tests use `aprkb_test` on port 55433 only, never the real database on 55432.
- Leave the existing gold-label edits alone. Do not commit or push unless the owner asks.
- Provisional lists carry `TODO(owner, FR-06.2)`.

## 5. Files

| Action | File (under `apps/backend/`) | Purpose |
|---|---|---|
| New | `src/aprkb/policies/hybrid_constructions.yaml` | Families, Meta-NP, boundary settings |
| New | `src/aprkb/modules/mining/stages/hybrid_slot_engine.py` | Engine; split only if it exceeds about 500 lines |
| New | `scripts/mining_coverage_report.py` | Repeatable counts-only corpus run and baseline diff |
| New | `tests/unit/mining/test_hybrid_slot_engine.py` | Family, gate, and control-flow tests |
| Edit | `src/aprkb/policies/schemas.py`, `loader.py` | `HybridConstructionsPolicy`, `is_safe_hybrid_frame`, `PolicyBundle.hybrid_constructions` |
| Edit | `src/aprkb/modules/mining/stages/construction_matcher.py` | Only `ReportingWithConstruction`: optional third step |
| Edit | `src/aprkb/modules/mining/stages/__init__.py`, `base.py`, `clusterer.py` | Switch, `canonical_skeleton`, skeleton in key |
| Edit | `src/aprkb/core/config.py`, repo `.env.example` | `MINING_HYBRID_ENABLED`, default false |
| Edit | `src/aprkb/worker/handlers.py`, `modules/mining/candidate_writer.py` | Pass switch and policy; writer path |
| Edit | `modules/review/service.py`, `modules/review/router.py`, `modules/extraction/service.py` | Accept hybrid frames |
| Edit | `tests/fixtures/nlp_spike/sentences.yaml`, `token_snapshots.json` | New fixtures through `scripts/generate_nlp_token_snapshots.py` |

## 6. Phases

Work through them in one pass. Run ruff and the unit suite at the end of each phase.

### Phase 0. Preflight

1. Copy `plans/hybrid-slot-engine/{spec.md,plan.md}` from the main worktree into the spike worktree.
2. Confirm branch and record `git status`.
3. Run baseline from `apps/backend`: ruff, ruff format check, mypy, the unit suite with `NLP_ENGINE=regex`, and the unit suite in the spaCy venv (`tmp/phase3-spacy-venv`, spaCy 3.8.18). Put pytest basetemp under `%TEMP%`.
4. Stop and report if the baseline fails.

### Phase 1. Reproducible Tier 1 baseline

Create `scripts/mining_coverage_report.py`, read-only, reusing the trial plumbing in `scripts/mining_trial_report.py` (rights check, `parse_and_analyze`, `SpacyEngine`, `usable_tokens`).

- Input: the 51 rights-checked blobs, `--hybrid on|off`, optional `--baseline <file>`.
- Write down the identity recipe in the script docstring:
  - source identity = SHA-256 of `blob_key \x1f sentence_ordinal \x1f char_start`, UTF-8.
  - output hash = SHA-256 of `frame \x1f sorted slot name:type \x1f tense \x1f ownership \x1f construction_id \x1f cluster_key`.
- Output: a JSONL manifest of hashes only, plus counts by tier, family, and rejection reason. Sentences scanned, kept, extractions, distinct frames, cluster keys, and frames with document frequency >= 2.
- Save the baseline as `plans/hybrid-slot-engine/tier1-baseline.jsonl` and run twice to prove identical output.

### Phase 2. Wiring with an empty engine

1. `HybridConstructionsPolicy` with `extra="forbid"`: unique family IDs, compiled regexes, allowed dep/POS labels, known slot strategies, `min_content_tokens` per family (default 3).
2. YAML, version `0.1.0`:

   ```yaml
   # Provisional; TODO(owner, FR-06.2): approve.
   version: 0.1.0
   meta_np:
     heads: [accuracy, performance, role, effect, limitation, reduction, relationship]
     connectors: [of, in, "on", between, for]
   boundary:
     pre_comma_frontier: true
   families:      # order is priority
     - id: hybrid_reporting_spine
       min_content_tokens: 1
     - id: hybrid_discourse_gap
     - id: hybrid_extraposed_it
     - id: hybrid_participial_lead_in
     - id: hybrid_comparative_correlation
     - id: hybrid_copular_definitional
     - id: hybrid_passive_academic
   ```

   Specific families go first. The discourse-gap example is also a valid passive, and comparatives are also copular, so the order matters.

3. `HybridSlotEngine.match_item(item) -> MiningItem | None` that always misses for now, with `match_counts` and `rejection_counts` like `ConstructionMatcher`.
4. `ReportingWithConstruction(reporting, constructions, hybrid=None)`: after a construction miss, call hybrid only if it is set and `item.tokens is not None`.
5. `build_stages(*, policy_bundle, hybrid_enabled: bool = False)`. Only `worker/handlers.py` passes `settings.mining_hybrid_enabled`. Default-off keeps `evaluation.py`, `stats.py`, and existing tests unchanged.
6. Add `is_safe_hybrid_frame(frame, policy, cluster_key)`:
   - Candidates have no `construction_id` column, so read the ID from the `construction=<id>:<version>:` prefix of `cluster_key`. No migration.
   - The ID must be an enabled family.
   - Placeholders must be `[X]`, `[Y]`, `[Z]` in source order, with at least one and no two adjacent.
   - Literals contain no digits, citations, or all-caps acronyms.
7. Use it in `CandidateWriter` and at the three re-check sites in review and extraction. Do not relax their other checks. Unknown IDs stay rejected.

Tests: off equals Tier 1 output; Tier 2 not called after a Tier 1 hit; called on double miss; not called without tokens; a Tier 2 result cannot overwrite Tier 1; review accepts a hybrid frame and rejects an unknown ID.

### Phase 3. Engine core

Reuse `normalized_children_by_head`, `select_syntax_root`, `subtree_indices`, `subtree_span`, `validate_token_features`, `_extend_following_citation`, and `_definition`. Copy the source-preserving idea of `_replace_slot_spans`.

1. **Bottom-up Meta-NP:** visit NP heads bottom-up. Keep a configured head and connector literal, and make the complement a slot. Directly attached `relcl`/`acl` stays in the slot. Ambiguous attachment means no proposal.
2. **Boundary repair:** collect subtrees, drop unrelated clauses and pre-comma discourse frontiers, trim punctuation, keep citations with the slot. Offsets always come from the original text.
3. **Frame Invariant:** spans in bounds, ordered, non-overlapping; replacing them reconstructs the emitted frame exactly.
4. **Purity Gate:** reject literal tokens that are `PROPN`, numbers, years, percentages, citations, or all-caps acronyms. Function words pass by `pos`. Count literal `NOUN`/`VERB`/`ADJ`/`ADV`; require the family minimum, including a `VERB`, `ADJ`, or Meta-NP head noun. Reject adjacent slots.
5. Slot type: use the slot's head token, `VERB`/`AUX` with a finite clause means `CLAUSE`, otherwise `NOUN_PHRASE`. Do not copy the first-token logic in `_match_rule`.

### Phase 4. Seven families

Match on dependency shape. Add a lemma list only when a family cannot be disambiguated without it, and keep such lists in the YAML. Do not reuse the narrow lemma lists from the brainstorm draft.

| Family | Shape | Slots |
|---|---|---|
| Reporting-spine | Only when `SlotAbstractor.extractability_reason(text, tokens) == "subject_too_long"`: root lemma in reporting classes, `that` clause. Other Tier 1 reporting rejections (`unlisted_lead_in`, `unlisted_modifier`, `coordinated_reporting_verbs`, `unmatched_content`) stay rejected by this family | X subject, Y clause |
| Discourse gap | Gap cue (`little`, `few`, `rarely`, `no`, `lack`, `remain unclear`) on subject or predicate | Object or complement |
| Extraposed `it` | `it` as `nsubj` under an `AUX` root (not `expl`), `acomp` or `attr`, and `xcomp`/`ccomp` as a child of the **root**, not of the adjective | Object of the infinitive, or the clause |
| Participial lead-in | Initial `advcl` with `VBG`/`VBN`, comma, then main clause. A `by` phrase is dep `agent`, not `prep`: follow `advcl -> agent -> pobj` | Up to 3 |
| Comparative/correlation | `outperform`, `correlate`, `differ`, or `more/less/than/superior to/similar to` markers. Root may be `VERB` or `AUX` (`is higher than`: `acomp` then `prep`) | Up to 3 |
| Copular/definitional | Root `be`/`remain`/`become` with `attr` or `acomp`, Meta-NP applied. Root is `AUX` | Up to 3 |
| Passive | `VBN` root with `auxpass`. Subject is `nsubj` **or** `nsubjpass`. Method is a marker `prep`, an `agent`, or `using` as `xcomp`/`advcl` with its `dobj` | X subject, Y method object |

Probe result (2026-11-06, `en_core_web_sm`, spaCy 3.8.18, `21299c4`): the shapes above come from parsing the spec's examples. All seven positives produce valid, unrepaired tokens and are a Tier 1 double miss, so they reach Tier 2. Two traps:

- `ConstructionMatcher` only accepts a `VERB` root. Copular, extraposed, and `is higher than` sentences have an `AUX` root, so do not copy that check.
- The positive passive example has `Samples` as `nsubj`, not `nsubjpass`. Requiring `nsubjpass` would miss it.

Fixtures: use the spec's positive and negative examples, plus at least two more of each per family. Add them to `sentences.yaml` and regenerate snapshots. The existing 142 snapshot records must stay byte-identical.

If `en_core_web_sm` parses a spec example differently, adapt the family to the real parse. If the expected frame is unreachable, record that example in the report; do not fake tokens.

The seven rejection sentences in the spec stay as analyzed fixtures. If a family produces a valid frame for one, other than the long-subject case already expected, keep the behavior and list it in the report instead of adding a narrow exception.

### Phase 5. Metadata and clustering

1. Build the `MiningItem` as `ConstructionMatcher.match_item` does: `ExtractionOccurrence`, `construction_id`, `construction_version` = hybrid policy version.
2. `tense`: `SlotAbstractor._syntax_tense`. `modality`: the `MD` token. `ownership`: `infer_ownership(subject, previous_text, policy, section_code)`.
3. `slot_binding_fingerprint`: Tier 1's recipe. `ConstructionMatcher` leaves it `None`; hybrid must not.
4. Add `MiningItem.canonical_skeleton: str | None = None`: the frame with the finite root replaced by its lemma and configured auxiliaries/adverbs removed. Display frame, tense, slots, and offsets stay unchanged.
5. In `Clusterer._key`, use `item.canonical_skeleton or item.text` as the frame source. Tier 1 leaves it `None`, so its keys do not change. Tense remains in the key: different tense means a different cluster.

### Phase 6. Run, fix, document

1. Run with `--hybrid off` and diff against the baseline: zero differences.
2. Run with `--hybrid on`: every Tier 1 row must still match the baseline hash. Report new extractions per family.
3. Fix the most frequent rejection reasons and boundary errors. Inspect sentences only through the guarded private dump in `mining_trial_report.py`, and never copy them out.
4. Stop after two fix rounds, or earlier if a round adds under 5% more extractions, and hand results to the owner.
5. New ADR, `doc/adr/0014-hybrid-slot-engine.md`: open-world tier, Purity Gate without a word list, switch. Update `modules/mining/README.md`, `policies/README.md`, and the `SCAFFOLD_PRD.md` phase note. Propose `CLAUDE.md` wording in the report.
6. Write `plans/reports/261106-hybrid-slot-engine-report.md`, counts only, with the commands and results.

## 7. Done when

- [ ] 42 + 16 unit tests pass, and the full unit suite passes under regex and spaCy.
- [ ] `--hybrid off` has zero baseline differences; `--hybrid on` has zero Tier 1 differences; both repeat identically.
- [ ] Each of the seven families has at least 3 positive and 3 negative fixtures passing, or a documented parse exception.
- [ ] Every accepted Tier 2 candidate passes Frame Invariant, Purity Gate, and metadata checks.
- [ ] A hybrid candidate can be listed, opened, and approved through the existing review flow.
- [ ] ruff, format check, and mypy pass.
- [ ] Integration passes on `aprkb_test` in both engines, or the exact skipped checks are reported. Phase 8.1 hit a safety hook on the credential handoff, so ask the owner for it.
- [ ] The report gives coverage before and after, per family.

No numeric coverage or precision target gates this release. The 90%/80% targets stay future goals, and approval rate is not an accuracy measure.

## 8. Operating note

Tier 2 needs stored tokens. Articles ingested under `NLP_ENGINE=regex` have none, so hybrid stays idle for them. To use it on stored articles, set `NLP_ENGINE=spacy` and `MINING_HYBRID_ENABLED=true`, then reingest. `reingest_article` skips articles with reviewed candidates.
