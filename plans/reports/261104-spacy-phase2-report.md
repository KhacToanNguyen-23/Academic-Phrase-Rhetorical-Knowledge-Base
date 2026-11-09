# spaCy ingest phase 2 report

Date: 2026-11-04  
Branch/worktree: `feat/spacy-nlp-spike`, `D:\6_OJT\aprkb-spacy-spike`  
Scope: rule-first sentence boundaries, ingest storage, and token passthrough only. Phase 3 syntax consumers are not implemented.

## 1. Boundary resolver

`boundary_candidates(text, rules)` is a pure character-level function. It only emits positions
from the existing punctuation/blank-line boundary search, plus unspaced `word.Word` and numbered
heading line breaks. Each candidate is classified once, in priority order, as `SPLIT`, `NO_SPLIT`,
or `UNSURE`.

The same candidates drive both modes:

- regex mode resolves `UNSURE` with the existing conservative heuristics and returns the existing
  `SentenceSpan` shape plus `boundary_source`;
- spaCy mode sets `True` for `SPLIT`, `False` for `NO_SPLIT`, and `None` for `UNSURE` only at
  candidate token offsets. Every other token is forced to `False`, so the parser cannot introduce
  a sentence before `[12]` or at any other non-candidate position;
- a candidate that does not align to a token start is counted as an alignment miss and treated as
  `NO_SPLIT`. No text is logged.

The versioned policy is `0.1.0` in `apps/backend/src/aprkb/policies/sentence_rules.yaml`. The
24 self-authored development cases produced these candidate counts:

| Rule / decision | Count |
|---|---:|
| `sentence_punctuation / SPLIT` | 10 |
| `unspaced / SPLIT` | 2 |
| `question_exclamation / SPLIT` | 2 |
| `abbrev_starter / SPLIT` | 2 |
| `heading_line / SPLIT` | 1 |
| `blank_line / SPLIT` | 1 |
| `open_bracket / NO_SPLIT` | 1 |
| `heading_internal / NO_SPLIT` | 1 |
| `abbrev_digit / NO_SPLIT` | 5 |
| `lowercase_continuation / NO_SPLIT` | 4 |
| `unsure_punctuation / UNSURE` | 7 |
| `unsure_abbreviation / UNSURE` | 4 |
| `unsure_initial / UNSURE` | 1 |

The resolver results are:

| Configuration | Exact fixture cases |
|---|---:|
| Regex with shared rules | 24/24 |
| Round-2 parser-only `en_core_web_sm` baseline | 20/24 |
| Phase-2 hybrid `en_core_web_sm` | 24/24 |

This is a deliberate default-behavior change. Before phase 2, the regex splitter scored 16/24 on
this fixture; the shared rules now make the default `NLP_ENGINE=regex` score 24/24. That is an
improvement, but the fixture was authored alongside the rules, so 24/24 is not a quality estimate
for unseen papers. Newly ingested articles use the new boundaries. Existing articles retain their
stored sentence rows and old boundaries until an explicit re-ingest.

The hybrid run had `0` token-alignment misses. It correctly keeps citation brackets and `Approx. 40`
together, handles `ms. Latency`, preserves `1. Introduction` as a heading sentence, and splits
`CNNs.Our`, `et al. Our`, and `?`/`!` followed by uppercase text. The old splitter tests remain
unchanged and pass.

Boundary sources across the hybrid output were `rule:start` 24,
`rule:sentence_punctuation` 10,
`rule:unspaced` 2, `rule:question_exclamation` 2, `rule:abbrev_starter` 2,
`rule:heading_line` 1, `rule:blank_line` 1, and `parser` 5. The first sentence of each input is
always recorded as `rule:start`; only later `UNSURE` starts are recorded as `parser`.

## 2. Engine selection and ingest behavior

Added settings:

```text
NLP_ENGINE=regex       # default; no spaCy dependency
NLP_MODEL=en_core_web_sm
```

`NLP_ENGINE=regex` stores `nlp_features = NULL` and a versioned regex engine descriptor in
`articles.nlp_engine`. `NLP_ENGINE=spacy` loads the configured model once per worker process,
stores token features and `boundary_source` for every sentence, and records the spaCy/model/policy
metadata in `articles.nlp_engine`.

If spaCy or the configured model cannot be loaded, ingest returns an explicit error beginning with
`NLP_ENGINE=spacy requires spaCy and model ...`; it does not fall back to regex. Rights are checked
before the blob is read, and re-ingest uses the same path so sentences, features, boundary sources,
and engine metadata are replaced together.

Mining now receives `tokens: tuple[TokenFeature, ...] | None` in `MiningItem`. No mining stage reads
the field in this phase, and a unit test compares all candidate-relevant output with and without
stored tokens. Mining does not import spaCy.

The engine records `repaired: true` in sentence JSON when trimming removes a whitespace head or
when no parser ROOT survives and a fallback ROOT is needed. It also exposes a cumulative
`repaired_sentences` count. The expanded 24-case run produced `0` repaired sentences; a regression
test constructs a token whose head is a removed whitespace token and verifies that the synthetic
ROOT is marked in JSON rather than hidden.

## 3. Storage and migration

Added nullable columns:

| Table | Column | Purpose |
|---|---|---|
| `sentences` | `nlp_features JSONB` | schema-versioned compact token arrays and sentence-relative offsets |
| `sentences` | `boundary_source TEXT` | `rule:<id>` or `parser` |
| `articles` | `nlp_engine JSONB` | engine/model/component/policy metadata for the last ingest |

Token text is not duplicated. It is reconstructed from the sentence text and token offsets. The
current migration command reported one head before implementation: `0008_merge_heads`. The new
revision is `0009_nlp_ingest_features` with that revision as its parent. The vocabulary branch's
future `0009_merge_vocabulary` will need a merge revision when the branches meet; this phase does
not hide that graph conflict.

Offline Alembic verification generated `ALTER TABLE` statements for all three columns and reported
`0009_nlp_ingest_features (head)`.

## 4. Feature storage measurement

On the 24 self-authored cases, hybrid analysis produced 47 sentences and 358 tokens. The compact
`SentenceAnalysis.to_json()` payload averaged:

- 75.20 bytes per token;
- 572.83 bytes per sentence.

The payload contains offsets, POS/tag/dependency/head/lemma/morphology and schema metadata, but no
token text. This is only a development estimate; phase 2 does not make a JSONB-vs-table decision.

## 5. Verification

Project `uv` environment, without spaCy, using a writable temporary directory:

```powershell
$env:TEMP='D:/6_OJT/aprkb-spacy-spike/tmp/phase2-full-test-temp'
$env:TMP=$env:TEMP
uv run --directory apps/backend pytest
```

Result: `414 passed, 73 skipped, 1 warning`. The skipped tests are the existing PostgreSQL/acceptance
paths plus the optional spaCy module. The Windows temp directory was overridden, so the four
`PermissionError` failures from the earlier branch check did not recur.

Dedicated spaCy/backend venv setup used for the model and PostgreSQL runs:

```powershell
python -m venv 'D:/6_OJT/aprkb-spacy-spike/tmp/feedback-spacy-venv'
& 'D:/6_OJT/aprkb-spacy-spike/tmp/feedback-spacy-venv/Scripts/python.exe' -m pip install --upgrade pip==25.0.1
& 'D:/6_OJT/aprkb-spacy-spike/tmp/feedback-spacy-venv/Scripts/python.exe' -m pip install spacy==3.8.18 pytest==8.3.5 PyYAML==6.0.2 pydantic==2.13.4 ruff==0.8.6
& 'D:/6_OJT/aprkb-spacy-spike/tmp/feedback-spacy-venv/Scripts/python.exe' -m pip install 'https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl'
uv pip install --python 'D:/6_OJT/aprkb-spacy-spike/tmp/feedback-spacy-venv/Scripts/python.exe' -e apps/backend 'pytest-asyncio>=0.25'
# Run from D:/6_OJT/aprkb-spacy-spike/apps/backend.
$env:PYTHONPATH='D:/6_OJT/aprkb-spacy-spike/apps/backend/src;D:/6_OJT/aprkb-spacy-spike/apps/backend'
& 'D:/6_OJT/aprkb-spacy-spike/tmp/feedback-spacy-venv/Scripts/python.exe' -m pytest --confcutdir='tests/unit/nlp' tests/unit/nlp tests/unit/corpus/test_boundary_rules.py tests/unit/corpus/test_sentence_splitter.py tests/unit/mining/test_mining_tokens.py -q
```

The model wheel URL is pinned to `en_core_web_sm-3.8.0`. After installing the backend editable
package, the loaded versions were Python 3.12.10, spaCy 3.8.18, `en_core_web_sm` 3.8.0, pytest
9.2.0, pytest-asyncio 1.4.1.post1, PyYAML 6.0.2, and pydantic 2.13.4. The dedicated NLP run
passed `50 tests`; two pytest asyncio configuration warnings and two pytest cache warnings are
caused by this intentionally separate venv. No `scispacy` package was installed.

PostgreSQL verification used a separate Docker project because `make` is not installed in this
Windows environment and host port 5432 was unavailable. The equivalent setup and migration were:

```powershell
$env:POSTGRES_PORT='55433'
docker compose -p aprkb-phase2 --env-file .env.example up -d --wait postgres
$db = (Get-Content .env.example | Where-Object { $_.StartsWith('DATABASE_URL=') }).Substring(13).Replace('localhost:5432','localhost:55433')
$env:DATABASE_URL = $db -replace '/aprkb$','/aprkb_test'
$env:TEST_DATABASE_URL = $env:DATABASE_URL
uv run --directory apps/backend alembic -c alembic.ini upgrade head
```

Migration reached `0009_nlp_ingest_features`. The phase-2 integration set contains 20 tests
(core database, corpus ingest/mine, and article import). It passed in both modes, using the same
`DATABASE_URL`/`TEST_DATABASE_URL` setup above:

- `NLP_ENGINE=regex`: `20 passed` (including `nlp_features IS NULL`, engine metadata, and
  `rule:start` assertions);
- `NLP_ENGINE=spacy`, `NLP_MODEL=en_core_web_sm`: `20 passed` (including persisted token JSONB,
  valid offsets, engine metadata, and the existing mining path).

Static checks on the project environment passed:

- Ruff check: passed;
- Ruff format check: passed;
- mypy: passed, 179 source files;
- existing splitter/policy/features/mining unit set: `59 passed`;
- offline Alembic upgrade SQL: passed.

## 6. Open items for phase 3

- `SentenceFilter` and `SlotAbstractor` still ignore `MiningItem.tokens`; use them later for finite
  verb checks, auxiliary-chain tense and a `that`-clause fallback without changing current output
  until a reviewed gold set exists.
- The rule vocabulary and abbreviation policy are provisional (`0.1.0`). Real Computer Science/IT
  articles need reviewed boundary precision/recall, especially ambiguous initials, units and
  abbreviation-plus-uppercase cases.
- spaCy model/version and policy metadata are persisted, but no NER, embeddings, model training or
  article-quality claim is part of this phase.
- PostgreSQL-backed ingest/mine integration was run against `aprkb_test` in both `regex` and
  `spacy` modes; both passed 20/20. The test container uses a separate local Docker project and
  volume on host port 55433 because `make` and port 5432 were unavailable in this Windows session.
- The temporary venv and benchmark/temp directories are local artifacts and are not committed.
