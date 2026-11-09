# spaCy NLP phase 3 report

Date: 2026-11-04  
Branch/worktree: `feat/spacy-nlp-spike` / `D:\6_OJT\aprkb-spacy-spike`  
Status: implemented, uncommitted, pending owner review

## Environment and reproducibility

The committed snapshot was generated in a dedicated virtual environment. spaCy and
the model were not added to the normal project environment, and `scispacy` was not
installed.

```powershell
py -3.12 -m venv tmp/phase3-spacy-venv
& tmp/phase3-spacy-venv/Scripts/python.exe -m pip install pip==25.0.1
& tmp/phase3-spacy-venv/Scripts/python.exe -m pip install spacy==3.8.18 PyYAML==6.0.2
& tmp/phase3-spacy-venv/Scripts/python.exe -m pip install `
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
uv pip install --python tmp/phase3-spacy-venv/Scripts/python.exe -e apps/backend
& tmp/phase3-spacy-venv/Scripts/python.exe apps/backend/scripts/generate_nlp_token_snapshots.py
```

Recorded versions are Python 3.12.10, pip 25.0.1, spaCy 3.8.18,
`en_core_web_sm` 3.8.0, PyYAML 6.0.2, and pydantic 2.13.4. The model wheel URL
is the URL shown above. The committed snapshot records the model and spaCy
versions.

For the normal suite I used the project backend environment, without spaCy:

```powershell
cd apps/backend
& .venv/Scripts/python.exe -m pytest -q
```

`make` is not installed in this Windows environment, and `uv run` could not
acquire its user cache lock. The equivalent direct commands were used for the
verification below; this is an environment limitation, not a test failure.

## Model and implementation decisions

Phase 3 keeps `en_core_web_sm` as the default model. Mining does not import
spaCy: it consumes the stored `TokenFeature` data, validates offsets/heads/ROOT,
and falls back to the existing regex locator when the data is absent or invalid.

`SentenceFilter` now has the policy-controlled `syntax_filter.require_finite_verb`
gate and rejects non-verbal roots. Both stages use the shared `select_syntax_root`
helper, which promotes a unique direct `acl` with a directly marked clause beneath
a nominal ROOT. `SlotAbstractor` uses the lexicon lemma as the
authority, the ROOT subject subtree, a direct `mark=that` child of its clause,
literal auxiliary/negation/adverb modifiers, and finite-verb-group tense. Coordinated
reporting verbs are rejected with a counted reason rather than guessed.
Analyses marked `repaired` are deliberately not passed to syntax mining and use
the regex path instead. Syntax clause spans exclude `that`, which remains literal
in the canonical frame, matching regex frame shape.

`mining_filter.yaml` and `reporting_verbs.yaml` are both version `0.3.0`.
Syntax-produced mining keys include `syntax:en_core_web_sm:3.8.0`; regex-produced
keys preserve the phase-2 key material.

## SentenceFilter measurement

On the 10 existing `slot_cases`, 0 were rejected by the new syntax rules (10/10
remain accepted). The two self-authored filter cases were both rejected with
`no_finite_verb`:

| Case | Result |
| --- | --- |
| `1. Introduction` | `no_finite_verb` |
| `A short fragment.` | `no_finite_verb` |

This is a fixture/design check, not a quality measurement. The fixtures were
written and tuned alongside these rules; quality evaluation remains a gold set on
real articles.

The full stage-list regression confirms `The fact that the model converges
suggests that the method is robust to noise.` passes the filter and extracts;
`These findings suggest a model that indicates that noise matters.` produces no
mining result.

## Regex versus syntax locator

The comparison covers the 10 existing slot fixtures plus the promoted-subject
regression and uses the committed spaCy snapshot. The categories are:

| Category | Count |
| --- | ---: |
| Both extract and equal | 0 |
| Both extract and differ | 6 |
| Only regex | 1 |
| Only syntax | 2 |
| Neither | 2 |

The reviewed differences and non-extractions are:

| Fixture | Outcome | Explanation |
| ---: | --- | --- |
| 1 | Both, different | The syntax subtree slot span excludes the final period; regex includes it in the span. |
| 2 | Only syntax | The dependency ROOT is `show`; regex selected a longer reporting form containing `proposed`. |
| 3 | Only syntax | The dependency ROOT is `show`; regex selected the parenthetical `demonstrated` form. |
| 4 | Both, different | The syntax subtree slot span excludes the final period; regex includes it in the span. |
| 5 | Both, different | The syntax subtree slot span excludes the final period; regex includes it in the span. |
| 6 | Both, different | Frame strings match. Syntax uses the finite passive auxiliary for present tense and narrows the subject to `It`; regex uses the lexical participle and reports past. |
| 7 | Only regex | spaCy attached `mark=that` under the clause subject instead of as a direct child of the ROOT clause; the strict locator returns `no_that`. |
| 8 | Neither | The `that` is a relative-clause subject, not a direct child marker on the ROOT clause. |
| 9 | Both, different | The syntax subtree slot span excludes the final period; regex includes it in the span. |
| 10 | Neither | The ROOT lemma is not in the reporting-verb lexicon. |
| 11 | Both, different | Promoted subject and clause are extracted; the syntax subtree slot span excludes the final period. |

Two added regression cases exercise the direct-child condition. `These findings
suggest a model that indicates that noise matters.` returns `no_that`, because the
marker is buried under a relative clause. For `The fact that the model converges
suggests that the method is robust to noise.`, spaCy 3.8.0 labels `fact` as the
dependency ROOT and attaches reporting `suggests` as its `acl`; the syntax locator
promotes that unique reporting `acl` only when it directly owns a clause with a
direct `mark=that`, using the nominal parent as the subject. The resulting slots
are exactly `The fact that the model converges` and `the method is robust to
noise`. The `that` marker remains in the canonical frame. Marker recognition
itself remains limited to the clause's direct children.

The parity test asserts frame-string equality for every fixture both paths
extract. Canonical frames keep the literal `that` connector and use the regex
locator's frame verb where available. The allow-list covers remaining differences
in slots, tense, ownership and spans; an unlisted difference fails the test.
For `The fact ... suggests ...`, both paths extract the same frame and the syntax
subtree slot span excludes the final period.

## Reason counts and fallback

The self-authored syntax cases produce three `no_that`, one
`coordinated_reporting_verbs`, and one `no_reporting_verb`. The validation test
corrupts offsets, creates two ROOTs, and supplies empty tokens; all three cases
fall back to regex and increment `syntax_invalid_tokens` (count 3). The two
filter fixtures add two `no_finite_verb` results. No source text or token text is
logged by these counters. The committed snapshot has no repaired analysis; the
production path still suppresses syntax use for the `repaired=true` contract.

## Tests and integration

The backend suite completed with:

```text
430 passed, 74 skipped, 2 warnings
```

The skipped tests include spaCy-marked tests because spaCy is intentionally not
installed in the normal environment. The phase-3 syntax regression/parity file
completed with 16 passed, including the two direct-marker cases and the parity
comparison for the 10 existing fixtures plus the promoted-subject regression.

The PostgreSQL integration used the existing healthy container on port 55433,
`TEST_DATABASE_URL` pointing to `aprkb_test`, and ran the same two selected
ingestion tests in each mode:

```powershell
$db = (Get-Content -LiteralPath 'D:/6_OJT/aprkb-spacy-spike/.env.example' |
  Where-Object { $_.StartsWith('DATABASE_URL=') }).Substring(13).Replace('localhost:5432','localhost:55433')
$env:DATABASE_URL = $db -replace '/aprkb$','/aprkb_test'
$env:TEST_DATABASE_URL = $env:DATABASE_URL

# regex
$env:NLP_ENGINE='regex'
& .venv/Scripts/python.exe -m pytest tests/integration/corpus/test_ingestion_jobs.py `
  -k 'selected_nlp_contract or parenthetical_reporting' -q
# result: 2 passed, 9 deselected

# spaCy, from tmp/phase3-spacy-venv with NLP_MODEL=en_core_web_sm
& D:/6_OJT/aprkb-spacy-spike/tmp/phase3-spacy-venv/Scripts/python.exe -m pytest `
  tests/integration/corpus/test_ingestion_jobs.py `
  -k 'selected_nlp_contract or parenthetical_reporting' -q
# result: 2 passed, 9 deselected
```

The full PostgreSQL integration suite was also run with the same database:

```powershell
& .venv/Scripts/python.exe -m pytest tests/integration -q
# result: 68 passed

& D:/6_OJT/aprkb-spacy-spike/tmp/phase3-spacy-venv/Scripts/python.exe -m pytest `
  tests/integration -q
# result: 68 passed
```

Both full integration runs passed. The warnings are the existing Starlette/httpx
deprecation and pytest cache-permission warnings.

Lint/type checks used the backend environment:

```powershell
& .venv/Scripts/ruff.exe check --no-cache .
& .venv/Scripts/ruff.exe format --check --no-cache .
& .venv/Scripts/mypy.exe --no-incremental `
  --cache-dir D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/tmp/aprkb-phase3-mypy-cache `
  src/aprkb
```

All three passed. `git diff --check` also passed.

## Open items for phase 2 follow-up / phase 3 review

- Define the sub-sentence collocation phrase boundary before adding a locator.
- Review modal tense handling (`TODO(owner, FR-06.2)`) against gold data.
- Decide whether coordinated reporting verbs should remain rejected or receive an
  explicit representation.
- Decide whether candidate metadata should persist the syntax locator.
- Evaluate quality only on reviewed real-article gold data; this report makes no
  real-corpus quality claim.
