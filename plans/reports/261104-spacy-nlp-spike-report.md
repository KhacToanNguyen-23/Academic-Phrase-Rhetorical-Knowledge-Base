# spaCy NLP spike report

Date: 2026-11-04  
Requirement: FR-06.2  
Scope: shared token features and source offsets only; no ingest, database, worker, or mining integration.

## 1. Versions and installation

Measured with Python 3.12.10, spaCy 3.8.18, scispaCy 0.6.2, `en_core_sci_sm` 0.5.4, and `en_core_web_sm` 3.8.0. PostgreSQL was not required or used.

Commands that worked:

```text
python -m pip install "spacy>=3.8,<3.9" "scispacy==0.6.2"
python -m pip install --no-deps --no-build-isolation "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz"
```

Installation attempts that were recorded:

- `python -m pip install "scispacy==0.5.5"` installs, but forces spaCy 3.7.5. It was reverted because the spike requires spaCy 3.8 and the plan says not to downgrade.
- `python -m pip install "spacy>=3.8,<3.9" "scispacy==0.6.2"` restored spaCy 3.8.18 and installed scispaCy 0.6.2.
- The presumed `en_core_sci_sm-0.6.2.tar.gz` and `en_core_sci_sm-0.6.0.tar.gz` URLs returned HTTP 404. The available 0.5.4 model was installed without dependencies to avoid another spaCy downgrade.
- The 0.5.4 model declares spaCy `<3.8.0` and emits a compatibility warning under spaCy 3.8.18. In the original `config.cfg`, `components.tok2vec.model.embed.include_static_vectors` is the string `"False"`; the exact load-time override is the boolean `False` at that same path. No override is applied when the original value is already a boolean, and no model files are committed or modified.

The comparison command is:

```text
cd apps/backend
python scripts/nlp_spike_compare.py
```

The benchmark was run with the system Python 3.12.10 environment containing the ad-hoc spaCy/scispaCy installs above. The project `uv run` environment intentionally has no spaCy extra and was used for the no-spaCy test/lint gate; no `uv pip install` package was left in the project lockfile. This distinction is required because `uv run` syncs the project environment from the lockfile and removes ad-hoc packages.

## 2. Sentence splitting

The fixture has 23 self-authored cases. Exact means the complete trimmed sentence list matched the hand-written expected list.

| Configuration | Exact cases | Total |
|---|---:|---:|
| Current regex splitter | 16 | 23 |
| `en_core_web_sm`, shared rules, no guard | 19 | 23 |
| `en_core_web_sm`, shared rules, abbreviation guard | 19 | 23 |
| `en_core_sci_sm`, shared rules, abbreviation guard | 21 | 23 |

Failing cases:

| Configuration | Case | Observed issue |
|---|---:|---|
| Regex | 6 | Does not split `CNNs.Our`. |
| Regex | 8 | Does not split after lowercase unit `ms.`. |
| Regex | 10 | Splits `No.` from `5`. |
| Regex | 12 | Splits `1.` from `Introduction`. |
| Regex | 16 | Splits after `Jan.` instead of preserving the date phrase. |
| Regex | 21 | Does not split after `et al.` before `Our`. |
| Regex | 23 | Does not split `CNNs.Our`. |
| Web, shared rules, no guard | 8 | Misses the lowercase `ms.` boundary. |
| Web, shared rules, no guard | 12 | Splits the numeric heading as `1.` and `Introduction`. |
| Web, shared rules, no guard | 13 | Splits after `Approx.`. |
| Web, shared rules, no guard | 15 | Splits between `BERT` and `[12]`. |
| Web, shared rules, guard | 8 | Misses the lowercase `ms.` boundary. |
| Web, shared rules, guard | 12 | Splits the numeric heading as `1.` and `Introduction`. |
| Web, shared rules, guard | 13 | Splits after `Approx.`. |
| Web, shared rules, guard | 15 | Splits between `BERT` and `[12]`. |
| Sci, shared rules, guard | 7 | Does not split after `?`. |
| Sci, shared rules, guard | 18 | Does not split the two clauses after `X.`. |

All three model configurations include the same custom component before the parser. The component always enables blank-line, numeric-heading, and unspaced-uppercase rules; `abbreviation_guard=False` disables only policy-abbreviation handling. Therefore the no-guard web row is not a raw spaCy baseline. The component uses the packaged abbreviation policy. For the ambiguous `ms`, lowercase `ms.` is treated as a unit and may end a sentence; capitalized `Ms.` is treated as the title and is guarded. For `al.` and `etc.`, a capitalized known sentence starter such as `Our` or `We` is allowed to begin a new sentence; otherwise the abbreviation is guarded. The sci tokenizer keeps `CNNs`, `.`, and `Our` as separate tokens, so the unspaced-uppercase rule is effective for that case.

## 3. Syntax probe for reporting-verb cases

Each model cell is `ROOT (morph) / nsubj subtree / ccomp`; `that*` means the ccomp has `mark=that`. Regex is the current `SlotAbstractor` result. In this table, `same` is an explicit equality with the immediately preceding model cell, not an unmeasured value.

| # | Self-authored sentence | Current regex | Web shared rules, no guard | Web shared rules, guard | Sci shared rules, guard |
|---:|---|---|---|---|---|
| 1 | These results suggest that the method is robust to noise. | extractable / suggest | suggest (Tense=Pres, VerbForm=Fin) / `These results suggest that the method` / `that the method is robust to noise`* | same | same |
| 2 | Our experiments clearly show that the proposed model converges faster. | no_that / proposed | show (Tense=Pres, VerbForm=Fin) / `Our experiments` / `that the proposed model converges faster`* | same | same |
| 3 | We show that the gain, as Lee demonstrated, is stable across all tested settings. | no_that / demonstrated | show (Tense=Pres, VerbForm=Fin) / `We show that the gain, as Lee demonstrated` / `that the gain, as Lee demonstrated, is stable across all tested settings`* | same | subject subtree keeps the comma: `We show that the gain, as Lee demonstrated,`; same ROOT/ccomp* |
| 4 | Previous studies have reported that larger batches reduce variance. | extractable / have reported | reported (Aspect=Perf, Tense=Past, VerbForm=Part) / `Previous studies have reported that larger batches` / `that larger batches reduce variance`* | same | same |
| 5 | The analysis did not reveal that the effect depends on sample size. | extractable / reveal | reveal (VerbForm=Inf) / `The analysis did not reveal that the effect` / `that the effect depends on sample size`* | same | same |
| 6 | It is widely argued that transfer learning reduces annotation cost. | extractable / argued | argued (Aspect=Perf, Tense=Past, VerbForm=Part) / `It is widely argued that transfer learning` / `that transfer learning reduces annotation cost`* | same | same |
| 7 | These findings may indicate that the baseline was undertrained. | extractable / indicate | indicate (VerbForm=Inf) / `These findings may indicate that the baseline` / `that the baseline was undertrained` | same, no `mark=that` | indicate (VerbForm=Inf) / same subject / `that the baseline was undertrained`* |
| 8 | In this paper, we propose a framework that unifies both objectives. | no_that / propose | propose (Tense=Pres, VerbForm=Fin) / `we propose a framework that` / no ccomp | same | same |
| 9 | Smith et al. (2020) found that accuracy drops under domain shift. | extractable / found | found (Tense=Past, VerbForm=Fin) / `Smith et al. (2020) found that accuracy` / `that accuracy drops under domain shift`* | same | same |
| 10 | The proposed approach significantly improves classification accuracy. | no_that / proposed | improves (Number=Sing, Person=3, Tense=Pres, VerbForm=Fin) / `The proposed approach` / no ccomp | same | same |

Case 3 is the central longest-form bug: the regex selects `demonstrated` inside the parenthetical instead of the main ROOT `show`, so it returns `no_that`. All parser configurations identify `show` as ROOT and expose a `that` ccomp. Case 10 exposes the syntactic distinction needed for the later rule: both parser configurations attach `classification` to `accuracy` with `dep=compound` and attach `proposed` to `approach` with `dep=amod`; the regex selects `proposed` and returns `no_that`.

## 4. Performance

The fixture texts were repeated to 5,000 inputs and parsed in three runs. Each model row produced at least 5,000 sentence analyses; the exact output count reflects the model's splitting decisions.

| Configuration | Parsed sentences | Inputs | Average ms / 1,000 sentences | Model load ms |
|---|---:|---:|---:|---:|
| Regex splitter | 9,592 | 5,014 | 3.80 | n/a |
| `en_core_web_sm`, shared rules, no guard | 10,464 | 5,014 | 580.53 | 1,253.23 |
| `en_core_web_sm`, shared rules, guard | 10,464 | 5,014 | 578.48 | 392.41 |
| `en_core_sci_sm`, shared rules, guard | 9,592 | 5,014 | 729.00 | 428.75 |

The timings are local spike measurements, not production capacity targets. `analyze_many` uses `nlp.pipe`.

## 5. Storage estimate

For the guarded `en_core_sci_sm` output, compact JSON serialization averaged 73.0 bytes per token and 556.1 bytes per sentence across 44 parsed fixture sentences. Token text is not stored; it is recovered from source offsets. The estimate excludes database JSONB page overhead, indexes, and row headers.

## 6. Findings and recommendation

- Adopt `en_core_sci_sm` for phase 2 only after owner approval because it reached 21/23 exact fixture cases versus 19/23 for either web configuration and 16/23 for the current regex splitter. The current code default is evidence-backed only after this benchmark; runtime wiring remains out of scope.
- Keep the shared boundary component and policy-driven abbreviation guard. It fixes `CNNs.Our`, `et al. Our`, and `etc. We` while preserving the `e.g.` and `No.` abbreviation cases. The scientific model still needs explicit handling for question boundaries and the two-clause `X. These` case.
- Preserve the `ms` policy decision: lowercase unit `ms.` may end a sentence; capitalized `Ms.` remains guarded. This is intentionally a narrow heuristic and should be covered by future ingest acceptance tests.
- Keep the exact source-offset contract and persist the engine/model metadata with any future ingest run. The parser offsets passed all fixture token checks, and every sentence had one ROOT with heads inside its sentence.
- Do not wire this spike into runtime yet. The `en_core_sci_sm` 0.5.4 model is operational under the current spaCy 3.8 environment only with the documented type-only load override and emits a model-built-for-3.7 compatibility warning. A phase-2 implementation should either obtain a model release compatible with spaCy 3.8 or pin the complete NLP environment deliberately after owner review.
