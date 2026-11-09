# spaCy NLP spike — round 2 report

Date: 2026-11-04  
Scope: self-authored fixtures only; no article corpus text, ingest wiring, worker wiring, or database changes.

## 1. Environment and reproducibility

The comparison was run in a dedicated virtual environment under the repository's ignored `tmp/` directory. No package was installed into system Python, and `scispacy` was not installed.

Exact setup commands used in PowerShell:

```powershell
python -m venv 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/nlp-spike-round2-venv'
& 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/nlp-spike-round2-venv/Scripts/python.exe' -m pip install --upgrade pip==25.0.1
& 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/nlp-spike-round2-venv/Scripts/python.exe' -m pip install spacy==3.8.18 pytest==8.3.5 PyYAML==6.0.2 pydantic==2.13.4 ruff==0.8.6
& 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/nlp-spike-round2-venv/Scripts/python.exe' -m pip install 'https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl'
```

Versions actually loaded:

| Item | Version |
|---|---:|
| Python | 3.12.10 |
| pip | 25.0.1 |
| spaCy | 3.8.18 |
| `en_core_web_sm` | 3.8.0 |
| pytest | 8.3.5 |
| PyYAML | 6.0.2 |
| pydantic | 2.13.4 |
| ruff | 0.8.6 |
| scispacy | not installed |

Commands used for the spaCy-side checks:

```powershell
$env:PYTHONPATH='D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/apps/backend/src'
& 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/nlp-spike-round2-venv/Scripts/python.exe' -m pytest --confcutdir='tests/unit/nlp' tests/unit/nlp -q
& 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/nlp-spike-round2-venv/Scripts/ruff.exe' check src/aprkb/nlp scripts/nlp_spike_compare.py tests/unit/nlp
& 'D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/nlp-spike-round2-venv/Scripts/python.exe' scripts/nlp_spike_compare.py
```

`--confcutdir=tests/unit/nlp` avoids loading unrelated project fixtures that require packages not installed in this minimal NLP venv. The project-level checks were run separately with the existing `uv` environment.

## 2. Model decision and implementation changes

Round 2 uses `en_core_web_sm` as the engine default. `SpacyEngine` and `get_engine` now default to this model, and `spacy.load(..., exclude=("ner",))` is used without a model-specific config override. The former `en_core_sci_sm`/`include_static_vectors` override was removed from `src/aprkb/nlp/`; the comparison script no longer loads a sci model.

This avoids changing a model's trained network at load time and avoids the round-1 compatibility warning for `en_core_sci_sm` 0.5.4 built for spaCy 3.7.x while running on spaCy 3.8. Round 2 does not create held-out fixtures; evaluation on real papers is deferred to the phase-2 gold set.

The comparison still runs three configurations:

1. current regex splitter;
2. `en_core_web_sm` with the shared deterministic sentence rules and `abbreviation_guard=False`;
3. `en_core_web_sm` with the same shared rules and `abbreviation_guard=True`.

Therefore configuration 2 is not raw spaCy: blank-line, heading, unspaced-boundary, and `?`/`!` rules are enabled in both spaCy configurations. The only difference between 2 and 3 is the abbreviation guard.

## 3. Sentence splitting

The fixture contains 24 sentence cases, including the three requested `et al.`, `e.g./etc.`, and `CNNs.Our` cases, plus the parenthesized question case. Exact-match results:

| Configuration | Exact cases | Total |
|---|---:|---:|
| Regex splitter | 16 | 24 |
| `en_core_web_sm`, shared rules, no guard | 20 | 24 |
| `en_core_web_sm`, shared rules, guard | 20 | 24 |

The new terminal rule is implemented as: `?` or `!`, followed by whitespace, followed by an uppercase letter. Fixture case 7 now splits into three sentences. The tokenizer keeps `CNNs.Our` as `CNNs`, `.`, `Our`, so the existing unspaced-boundary rule can run; this is covered by the tokenizer test. The parenthesized question case remains one sentence because the closing delimiter is protected from the outer `?`/`!` rule.

Remaining failures for both `en_core_web_sm` configurations:

| Case | Expected issue | Observed result |
|---:|---|---|
| 8 | Split after unit `ms.` | `ms. Latency` remains one sentence |
| 12 | Keep `1. Introduction` as one heading sentence | `1.` and `Introduction` are separated |
| 13 | Keep `Approx. 40` together | `Approx.` and `40 samples...` are separated |
| 15 | Keep citation bracket inside one sentence | A split occurs before `[12]` |

Regex-only failures are cases 6, 8, 10, 12, 16, 21, 23, and 24. The regex baseline therefore remains better for a few existing edge cases, while the spaCy configurations handle the new punctuation and unspaced-boundary cases more consistently.

## 4. Corrected syntax measurement

The comparison helper now selects only a subject dependency directly attached to the sentence ROOT (`nsubj`, `nsubjpass`, or the explicit subject fallback `expl`) and only a `ccomp` directly attached to ROOT. Each span is the single token's subtree, from `left_edge` through `right_edge`, with trailing punctuation trimmed. The no-guard and guard configurations produced the same syntax rows below.

| # | ROOT + morph | Direct-ROOT subject | Direct-ROOT `ccomp` |
|---:|---|---|---|
| 1 | `suggest` (`Tense=Pres\|VerbForm=Fin`) | `nsubj: These results` | `that the method is robust to noise` (`mark=that`) |
| 2 | `show` (`Tense=Pres\|VerbForm=Fin`) | `nsubj: Our experiments` | `that the proposed model converges faster` (`mark=that`) |
| 3 | `show` (`Tense=Pres\|VerbForm=Fin`) | `nsubj: We` | `that the gain, as Lee demonstrated, is stable across all tested settings` (`mark=that`) |
| 4 | `reported` (`Aspect=Perf\|Tense=Past\|VerbForm=Part`) | `nsubj: Previous studies` | `that larger batches reduce variance` (`mark=that`) |
| 5 | `reveal` (`VerbForm=Inf`) | `nsubj: The analysis` | `that the effect depends on sample size` (`mark=that`) |
| 6 | `argued` (`Aspect=Perf\|Tense=Past\|VerbForm=Part`) | `nsubjpass: It` | `that transfer learning reduces annotation cost` (`mark=that`) |
| 7 | `indicate` (`VerbForm=Inf`) | `nsubj: These findings` | `-` |
| 8 | `propose` (`Tense=Pres\|VerbForm=Fin`) | `nsubj: we` | `-` |
| 9 | `found` (`Tense=Past\|VerbForm=Fin`) | `nsubj: Smith et al. (2020)` | `that accuracy drops under domain shift` (`mark=that`) |
| 10 | `improves` (`Number=Sing\|Person=3\|Tense=Pres\|VerbForm=Fin`) | `nsubj: The proposed approach` | `-` |

The required case 1 now reports exactly `These results` and `that the method is robust to noise`. In case 3, spaCy reports ROOT `show` and subject `We`; the regex probe still chooses the parenthetical verb `demonstrated`, showing the original longest-form measurement problem. In case 10, `proposed` is `amod` of `approach`, while `classification` is `compound` of `accuracy`; the parse does not treat `classification accuracy` as an `amod` chain.

## 5. Tests, lint, and type checking

With the dedicated spaCy environment:

- NLP tests: `11 passed, 2 warnings`.
- Warnings: the minimal venv does not install the project's pytest-asyncio plugin configuration, so two unrelated asyncio config options are reported as unknown.
- Targeted ruff: passed.

With the project `uv` environment, where spaCy is not installed:

- Full pytest: `404 passed, 76 skipped, 2 warnings`.
- Targeted ruff: passed.
- Ruff format check: passed; 6 files already formatted.
- Mypy: passed, 189 source files checked.

The round-1 report file was left unchanged. No database or PostgreSQL setup was required for this spike.

## 6. Open limitations for phase 2

- The four remaining web-model fixture failures (`ms.`, numeric heading, `Approx.`, and citation bracket handling) need an explicit policy decision before ingest integration. No additional abbreviation rule was added in this round.
- The `?`/`!` rule is intentionally narrow: it requires whitespace and an uppercase next token, with the tested parenthesis/quote protection. It is not a general punctuation or quotation parser.
- The abbreviation guard is policy-driven and still needs broader gold-set evaluation, especially for ambiguous abbreviations such as `ms.` and sentence starters after `et al.`.
- The measurements are self-authored development fixtures, not a quality claim for real papers. Phase 2 should create a reviewed gold set on real Computer Science/IT articles and measure boundary and syntax precision/recall there.
- The engine remains a spike-only package. It is not wired into ingest, sentence persistence, mining, worker jobs, or database schema.
- The dedicated venv and benchmark output are temporary local artifacts and are not part of the commit.

