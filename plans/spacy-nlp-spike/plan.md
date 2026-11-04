# spaCy NLP spike — shared token features with source offsets

Status: approved for a spike by the owner (2026-11-04). Not approved for runtime integration.
Requirement: `FR-06.2` (spaCy deferred in ADR-0007; this spike produces the evidence for lifting that deferral).
Branch: create `feat/spacy-nlp-spike` from `dev`.

## 1. Why

The current pipeline is regex-only:

```
Ingest (worker):  parser → corpus/sentence_splitter.split_sentences → `sentences` rows (offsets)
Mine job:         SentenceFilter → move_classifier(TODO) → EpistemicTagger
                  → SlotAbstractor → FrameNormalizer → Clusterer → dedup_matcher(TODO)
```

Known weaknesses that syntax could fix:

- `SlotAbstractor._reporting_match` picks the **longest** matching verb form, not the main verb.
  `"We show that the gain, as Lee demonstrated, is stable across all tested settings."` matches
  `demonstrated` and the sentence is dropped as `no_that`.
- Subject = "everything before the verb"; clause = "everything after `that`". Slot types are
  positional, not syntactic.
- Splitter errors on `No. 5 …`, `Jan. and Mar. 2021.`, `in ms. Latency …`, `CNNs.Our …`,
  `1. Introduction\n…`.
- The filter cannot detect fragments or headings (no finite-verb check).

Agreed target design (option A, **later phase, not this spike**): run spaCy **once at ingest**,
use it for sentence boundaries, persist per-token features for each `Sentence` row, and let the
mining job read them back without re-parsing. Offsets must stay exact against the source text.

This spike builds and measures the shared NLP layer and its data contract only.

## 2. Scope

In scope:

1. A new infrastructure package `apps/backend/src/aprkb/nlp/` (no business logic).
2. A pure, serialisable token-feature contract that phase 2 will store in the DB.
3. A spaCy engine that turns a section text into sentences + token features with exact offsets.
4. Unit tests that are skipped when spaCy is not installed.
5. A comparison script and a written report with measurements.

Out of scope (do **not** do these):

- No Alembic migration, no model/table/column changes, no worker or ingest changes.
- Do not change behaviour of `split_sentences`, `SentenceFilter`, `SlotAbstractor`, `Clusterer`.
- No NER, no embeddings, no LLM, no `sentence-transformers` usage.
- Do not edit `SCAFFOLD_PRD.md`, ADR-0007, or `CLAUDE.md` (the owner updates scope after the report).
- No real article text in fixtures, tests, logs or the report. Use only the self-authored
  sentences in section 6. Never log sentence text from the engine.
- Do not commit model files or wheels.

## 3. Installation (spike only)

The `nlp` extra in `pyproject.toml` also pulls `sentence-transformers` (torch). Do not install the
whole extra for this spike, and do not change `pyproject.toml` dependencies.

```bash
cd apps/backend
uv pip install "spacy>=3.8,<3.9"
uv pip install <pinned en_core_web_sm wheel URL matching the installed spaCy minor version>
```

`python -m spacy download` relies on pip and usually fails inside uv environments; use the wheel
URL from the spaCy models GitHub release instead. Record exact versions in the report.

Optionally try scispaCy `en_core_sci_sm`. If it cannot be installed alongside spaCy 3.8, record
the conflict in the report and skip it; do not downgrade spaCy.

Note: `make install` (`uv sync`) removes ad-hoc packages. That is acceptable for the spike.

`make lint` and `make test` must pass **both with and without** spaCy installed:

- Import spaCy lazily inside the engine, never at package import time.
- Add a mypy override in `pyproject.toml` (`[[tool.mypy.overrides]]`, `module = ["spacy", "spacy.*"]`,
  `ignore_missing_imports = true`). This is the only `pyproject.toml` edit allowed.
- Tests use `pytest.importorskip("spacy")` and skip cleanly when the model is missing.

## 4. Package layout

```
apps/backend/src/aprkb/nlp/
  __init__.py        # re-exports the contract types and `get_engine`
  features.py        # pure dataclasses + (de)serialisation; must not import spaCy
  spacy_engine.py    # SpacyEngine; lazy spaCy import
apps/backend/tests/unit/nlp/
  test_features.py         # runs without spaCy
  test_spacy_engine.py     # importorskip("spacy")
apps/backend/scripts/
  nlp_spike_compare.py     # comparison script (not part of the package)
```

Every module docstring states `TODO(owner, FR-06.2): spike only; not wired into ingest or mining.`

## 5. Data contract (`features.py`)

This is the shape phase 2 will persist per `Sentence`. Keep it small, stable and versioned.

```python
FEATURES_SCHEMA_VERSION = 1

@dataclass(frozen=True)
class TokenFeature:
    i: int          # index within the sentence (0-based)
    start: int      # char offset relative to the sentence start
    end: int        # exclusive; sentence_text[start:end] == token text
    pos: str        # coarse UPOS, e.g. "VERB"
    tag: str        # fine-grained tag, e.g. "VBD"
    dep: str        # dependency label, "ROOT" for the root
    head: int       # sentence-relative index of the head; root points to itself
    lemma: str
    morph: str      # e.g. "Tense=Past|VerbForm=Fin" (needed for the tense rule)
    is_space: bool  # whitespace tokens are kept so indices stay aligned

@dataclass(frozen=True)
class NlpEngineInfo:
    engine: str            # "spacy"
    spacy_version: str
    model_name: str
    model_version: str
    components: tuple[str, ...]
    schema_version: int    # FEATURES_SCHEMA_VERSION
    abbreviation_guard: bool

@dataclass(frozen=True)
class SentenceAnalysis:
    char_start: int        # offset into the analysed input text (same meaning as SentenceSpan)
    char_end: int
    tokens: tuple[TokenFeature, ...]
```

Rules:

- Do **not** store token text: it is derived from the sentence text and offsets. This avoids
  duplicating source text.
- Provide `to_json(...)` / `from_json(...)` for `SentenceAnalysis` (compact: a list of arrays per
  token is fine) and a lossless round-trip test.
- `SentenceAnalysis` must be convertible to the existing `SentenceSpan` (text, char_start,
  char_end) so it can later replace `split_sentences` without changing callers.

## 6. Engine (`spacy_engine.py`)

```python
class SpacyEngine:
    def __init__(self, model_name: str = "en_core_web_sm", *, abbreviation_guard: bool = True): ...
    @property
    def info(self) -> NlpEngineInfo: ...
    def analyze(self, text: str) -> list[SentenceAnalysis]: ...
    def analyze_many(self, texts: Iterable[str]) -> Iterator[list[SentenceAnalysis]]: ...  # nlp.pipe
```

Requirements:

- Load the model once per engine and exclude `ner` (NER is deferred).
- The input is one section's text, the same input `split_sentences` receives today.
- Offsets: for every token, `text[sent.char_start + tok.start : sent.char_start + tok.end]`
  must equal spaCy's `token.text`. Sentence `char_start`/`char_end` must be trimmed of
  surrounding whitespace exactly like `_append_span` does today.
- Heads must stay inside their sentence (assert it; spaCy guarantees it).
- `abbreviation_guard=True` adds a small custom component **before the parser** that sets
  `is_sent_start = False` on the token after a known abbreviation. Load the abbreviations from
  the existing policy (`load_policy_bundle().abbreviations`); do not create a new list.
  Treat `ms` carefully: it is both the title "Ms." and the unit "ms". Document what you chose.
- Blank lines (`\n\s*\n`) must always end a sentence, matching the current splitter.
- No logging of text. Log only counts and timings, if anything.

## 7. Self-authored fixtures

Create `apps/backend/tests/fixtures/nlp_spike/sentences.yaml`. Each case has `text` and
`expected` (the correct sentence list, written by hand). Use exactly these cases (they are
self-authored; do not add copied corpus text). You may add more self-authored cases.

| # | text | expected sentences |
|---|---|---|
| 1 | `Previous work (Smith et al., 2020) reported gains. However, they ignored noise.` | 2 |
| 2 | `Accuracy rose to 92.5% (see Fig. 3). This suggests robustness.` | 2 |
| 3 | `We used three datasets, i.e. MNIST, CIFAR and SVHN. Results are shown below.` | 2 |
| 4 | `The model was trained on the U.S. Census data. Then we evaluated it.` | 2 |
| 5 | `As shown in Table 2, our method wins. Section 4.1 describes it.` | 2 |
| 6 | `Prior studies [3, 5] used CNNs.Our approach differs.` | 2 (`…CNNs.` / `Our approach differs.`) |
| 7 | `Does this hold? We argue it does! Moreover, see Eq. (2).` | 3 |
| 8 | `Performance was measured in ms. Latency dropped by 30 ms on average.` | 2 |
| 9 | `We thank Dr. Nguyen for comments. Funding was provided by NSF.` | 2 |
| 10 | `Results were significant (p < 0.05). No. 5 participants dropped out.` | 2 |
| 11 | `The approach of Lee et al. outperforms baselines. Wang et al. disagree.` | 2 |
| 12 | `1. Introduction\nDeep learning has transformed vision. It now dominates.` | heading `1. Introduction` separate + 2 |
| 13 | `Fig. 2 shows the pipeline. Approx. 40 samples were removed.` | 2 |
| 14 | `This method is efficient; however, it scales poorly. We fix this.` | 2 |
| 15 | `Recent models (e.g., BERT [12]; GPT-3 [13]) achieve strong results.` | 1 |
| 16 | `Data were collected between Jan. and Mar. 2021. Analysis followed.` | 2 |
| 17 | `The F1-score improved from 0.71 to 0.84 (Δ = 0.13). This is large.` | 2 |
| 18 | `In contrast to [7], we find that X. These findings suggest that Y.` | 2 |
| 19 | `We define the loss as L = α·L1 + β·L2, where α, β ∈ [0, 1].` | 1 |
| 20 | `First paragraph ends here.\n\nSecond paragraph starts here.` | 2 |

Second fixture group, `slot_cases` (reporting-verb sentences, for the syntax probe):

1. `These results suggest that the method is robust to noise.`
2. `Our experiments clearly show that the proposed model converges faster.`
3. `We show that the gain, as Lee demonstrated, is stable across all tested settings.`
4. `Previous studies have reported that larger batches reduce variance.`
5. `The analysis did not reveal that the effect depends on sample size.`
6. `It is widely argued that transfer learning reduces annotation cost.`
7. `These findings may indicate that the baseline was undertrained.`
8. `In this paper, we propose a framework that unifies both objectives.`
9. `Smith et al. (2020) found that accuracy drops under domain shift.`
10. `The proposed approach significantly improves classification accuracy.`

## 8. Tests

`test_features.py` (no spaCy): JSON round-trip; `SentenceSpan` conversion; schema version present.

`test_spacy_engine.py` (`importorskip`):

- Offset invariant holds for every token of every fixture case (this is the most important test).
- Heads stay within the sentence; exactly one `ROOT` per sentence.
- Blank-line case (#20) yields 2 sentences.
- `info` reports real spaCy/model versions and `schema_version == 1`.
- Do **not** assert that every fixture splits as expected. Splitting quality is measured in the
  report, not enforced as a test (a test would just encode the model's current mistakes).

## 9. Comparison script and report

`scripts/nlp_spike_compare.py` loads the fixtures and prints a Markdown summary. Run it for:

- (a) the current regex `split_sentences`,
- (b) `en_core_web_sm` without the abbreviation guard,
- (c) `en_core_web_sm` with the abbreviation guard,
- (d) `en_core_sci_sm` with the guard, if installable.

Write the report to `plans/reports/261104-spacy-nlp-spike-report.md` with:

1. Exact versions and the install commands that worked (and any that failed).
2. Sentence splitting: per-config count of fixture cases split exactly as expected, plus a table
   of every failing case per config.
3. Syntax probe for `slot_cases`: for each sentence give, per spaCy config, the ROOT verb (+ morph
   tense), the `nsubj`/`nsubjpass` subtree span, the `ccomp` span with `mark=that` if any, and the
   current regex result (`SlotAbstractor.extractability_reason` and the matched verb). Highlight
   case 3 (the longest-form bug) and case 10 (`compound` vs `amod` for `classification accuracy`).
4. Performance: average parse time per 1,000 sentences on the fixtures repeated to at least
   5,000 sentences, and model load time.
5. Storage estimate for option A: average JSON bytes per token and per sentence.
6. Findings and a recommendation: which config to adopt for phase 2, what the abbreviation guard
   must still handle, and any regression versus the regex splitter.

The report may quote the self-authored fixture sentences. It must not contain any real article text.

## 10. Done when

- `make lint` and `make test` pass with spaCy **not** installed (spaCy tests skipped).
- `make lint` and `make test` pass with spaCy and `en_core_web_sm` installed (spaCy tests run).
- The report exists and covers all six sections.
- No changes outside: `src/aprkb/nlp/`, `tests/unit/nlp/`, `tests/fixtures/nlp_spike/`,
  `scripts/nlp_spike_compare.py`, the mypy override in `pyproject.toml`, the report, and a
  one-line pointer in `apps/backend/src/aprkb/modules/mining/README.md` noting the spike exists
  and is not wired in.
- If PostgreSQL is not available, say so; this spike needs no database.

## 11. Next phase (for context only; do not implement)

Phase 2, after owner review of the report: replace `split_sentences` at ingest with the engine,
persist `SentenceAnalysis` features per `Sentence` (JSONB column vs. separate table to be decided
using the storage estimate), store `NlpEngineInfo` with the article's ingest run, add the engine
and model versions to the `Clusterer` policy version, then let `SentenceFilter` and
`SlotAbstractor` read the stored features.

## 12. Round 2 — model decision and three cheap fixes

Status: approved by the owner on 2026-11-04 after reviewing the round-1 report. Same branch and
same scope limits as sections 2 and 10: no ingest/worker/DB wiring, no PRD/ADR edits, and only
self-authored text.

### 12.1 Model decision (owner)

Use **`en_core_web_sm`** as the engine's model. Reasons:

- It officially supports spaCy 3.8; no load-time override and no compatibility warning.
  `en_core_sci_sm` 0.5.4 needs a config override and warns that it was built for spaCy 3.7.
- The target corpus is Computer Science / IT papers. scispaCy is trained mainly on biomedical
  text, so it has no assumed advantage, and the round-1 scores (21/23 vs 19/23) were measured on
  dev fixtures that the rules were tuned on, so they cannot justify the extra cost.

A large held-out evaluation is **not** part of this spike. Real quality evaluation is deferred to
the gold set on real articles once it resumes. Do not create held-out files.

Changes:

- Set the default model of `SpacyEngine` and `get_engine` to `en_core_web_sm`.
- Remove the `en_core_sci_sm`-specific load-time config override from the engine. If keeping the
  sci model loadable for comparison is useful, keep that override only in
  `scripts/nlp_spike_compare.py`, not in `src/aprkb/nlp/`.
- Tests must run against `en_core_web_sm` and skip cleanly when it is not installed.

### 12.2 Fix the syntax measurement

`_subtree_text` in `scripts/nlp_spike_compare.py` merges the subtrees of *every*
`nsubj`/`nsubjpass` in the sentence, including the subject of the `that`-clause, so the reported
"subject" spills into the clause (case 1 shows `These results suggest that the method` instead of
`These results`). The `ccomp` column has the same flaw.

- Subject: take only the `nsubj`/`nsubjpass` token whose `head` is the sentence ROOT. For
  `It is … argued that …`, report the `expl`/`nsubjpass` token and say which one was used.
- Clause: take only the `ccomp` whose `head` is ROOT, and report whether it has `mark=that`.
- Span = from `left_edge.idx` to the end of `right_edge` of that single token's subtree, trimmed
  of trailing punctuation.
- Move this helper into a small testable function and add a unit test (with
  `importorskip("spacy")`) on case 1: expected subject `These results`, expected clause
  `that the method is robust to noise`.
- Re-run the 10 `slot_cases` with the fixed helper.

### 12.3 Add the `?` / `!` boundary rule

Add to the shared boundary component: `?` or `!`, then whitespace, then an uppercase letter →
always a sentence start. Cover it with the existing dev case 7 and one new self-authored case
where `?` is inside a quotation or parenthesis and must **not** split (for example
`The question ("does it scale?") remains open.`).

Do not add other new rules in this round.

### 12.4 Reproducible environment

- Do not install into the system Python. Create a dedicated virtual environment that is not
  committed (outside the repo or under a git-ignored path).
- Write the exact commands to create it in the report, including the pinned versions of `spacy`
  and the `en_core_web_sm` wheel URL, so that anyone can recreate the same environment.
- Do not install `scispacy` in this environment unless the comparison script needs the sci model;
  the engine does not import it.
- Run the NLP tests and the comparison script from that environment.
- `make lint` and `make test` in the project `uv` environment (no spaCy) must still pass.

### 12.5 Report

Write `plans/reports/261104-spacy-nlp-spike-round2-report.md` and leave the round-1 report
unchanged. Include:

1. Environment: the exact creation commands and versions from 12.4.
2. The model decision from 12.1 and the code changes it caused.
3. Dev-fixture sentence splitting for regex and `en_core_web_sm` (with the new `?`/`!` rule),
   including the remaining failing cases.
4. The corrected syntax table for the 10 `slot_cases` with `en_core_web_sm`, highlighting case 3
   (parenthetical second verb) and case 10 (`compound` vs `amod`).
5. Test and lint results, both with and without spaCy installed.
6. Known limitations, stated as open items for phase 2 (for example the remaining dev failures
   `ms.` and the numeric heading for the web model, if they still fail).

### 12.6 Done when

- The engine defaults to `en_core_web_sm` and has no sci-specific override in `src/aprkb/nlp/`.
- The subject/clause helper is fixed and unit-tested.
- The `?`/`!` rule exists with both dev fixtures.
- The dedicated environment is documented and reproducible.
- `make lint` and `make test` pass without spaCy; the NLP tests pass with `en_core_web_sm`.
- The round-2 report covers all six items.

