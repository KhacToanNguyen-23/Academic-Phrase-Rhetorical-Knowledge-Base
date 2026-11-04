# spaCy NLP — phase 2: rule-first sentence boundaries and stored token features at ingest

Status: approved by the owner on 2026-11-04 (option A; rule-first boundaries).
Requirement: `FR-06.2`, `FR-07`.
Branch: `feat/spacy-nlp-spike` (spike commit `b7110be`). Read `plan.md` sections 1–12 and both
spike reports first.

## 1. Decisions already made by the owner

1. **Option A.** spaCy runs **once at ingest**. Per-token features are stored with each
   `Sentence` row. The mining job reads them back and never re-parses.
2. **Model:** `en_core_web_sm` (official spaCy 3.8 support, no load-time override).
3. **Rule-first sentence boundaries.** spaCy alone is not reliable enough to split scientific
   text: in round 2 it failed `ms.`, `Approx. 40` and split before a citation `[12]`, all of which
   the regex splitter handles. Deterministic rules decide every boundary they are sure about;
   the spaCy parser decides **only** the boundaries the rules mark as unsure. spaCy's main job is
   to describe what is inside a sentence (POS, dependencies, lemma, morphology).

## 2. Scope

In scope:

1. Owner-facing docs that lift the spaCy deferral for ingest (section 3).
2. A tri-state boundary rule layer shared by the regex and spaCy paths (section 4).
3. A spaCy ingest path that stores token features per sentence (sections 5–6).
4. Passing stored features to mining as data, without changing mining behaviour (section 7).

Out of scope (phase 3): `SentenceFilter` and `SlotAbstractor` using the features (finite-verb
checks, tense from the `aux` chain, `that`-clause fallback when there is no direct `ccomp`).
Also out of scope: NER, embeddings, LLM, frontend, held-out evaluation.

Invariants that still apply: check mining rights before reading or parsing a blob; no article
text, sentence text, token text or lemma in logs or audit snapshots; fixtures stay self-authored.

## 3. Docs first

- Add `doc/adr/0010-spacy-ingest-token-features.md`: context (spike results), the three decisions
  in section 1, the tri-state boundary design, the storage format, the `NLP_ENGINE` setting, and
  what remains deferred (phase 3 items, NER). Link the spike reports.
- Update ADR-0007, `SCAFFOLD_PRD.md`, `README.md` and `apps/backend/src/aprkb/modules/mining/README.md`
  so they no longer say spaCy is fully deferred: spaCy is used at ingest behind `NLP_ENGINE`;
  syntax-based filtering and slot extraction remain `TODO(owner, FR-06.2)`.
- Keep the existing Vietnamese wording style in `SCAFFOLD_PRD.md`.

## 4. Tri-state boundary rules

Refactor `apps/backend/src/aprkb/modules/corpus/sentence_splitter.py` so that boundary logic is a
pure function over **characters** (not spaCy tokens; this also removes the round-2 bug where the
web tokenizer split `Approx.` into `Approx` + `.` and the guard flagged the wrong token):

```python
class BoundaryDecision(StrEnum):
    SPLIT = "split"        # rules are sure a sentence starts here
    NO_SPLIT = "no_split"  # rules are sure it does not
    UNSURE = "unsure"      # left to the resolver

@dataclass(frozen=True)
class BoundaryCandidate:
    offset: int            # char offset where the next sentence would start
    decision: BoundaryDecision
    rule: str              # short rule id, e.g. "blank_line", "abbrev_digit", "open_bracket"

def boundary_candidates(text: str, rules: SentenceRulesPolicy) -> list[BoundaryCandidate]: ...
```

Candidate positions are the places the current `_BOUNDARY` regex already finds (whitespace after
sentence punctuation or closers, blank lines), plus the unspaced `word.Word` case and line breaks
after a heading-like line. **No other position can start a sentence**, whatever the parser thinks.
This alone prevents the split before `[12]`.

Rules, in priority order (first match wins):

| Decision | Rule | Example |
|---|---|---|
| SPLIT | blank line | `…here.\n\nSecond…` |
| SPLIT | heading line (numbered, with or without trailing dot, short, no final punctuation) | `1. Introduction\n…`, `3.2 Training\n…` |
| NO_SPLIT | inside an open `(` or `[` that closes later in the text | `(e.g., BERT [12]; GPT-3 [13])` |
| NO_SPLIT | abbreviation followed by a digit or lowercase word | `No. 5`, `Approx. 40`, `Fig. 2`, `et al. reported` |
| NO_SPLIT | decimal, version, URL, DOI, e-mail, file name | `0.71`, `v2.1.0`, `example.org/a.b`, `config.yaml` |
| NO_SPLIT | initial followed by a capitalised surname | `J. Smith` |
| SPLIT | `?`/`!` + whitespace + uppercase (keep the parenthesis/quote protection) | `Does this hold? We argue…` |
| SPLIT | unspaced lowercase/plural `.` + uppercase word | `CNNs.Our` |
| SPLIT | `.` after a non-abbreviation word + whitespace + uppercase | `…gains. However…` |
| SPLIT | abbreviation (`al`, `etc`, units such as `ms`) + known sentence starter | `Lee et al. Our method…`, `in ms. Latency…` |
| UNSURE | anything else after an abbreviation, single letter or unit + uppercase word | `type A. Results…`, `Mar. 2021.` edge cases |

All vocabularies move into versioned YAML: keep `policies/lexicon/abbreviations.yaml`, and add
`policies/sentence_rules.yaml` (sentence starters, unit tokens, heading limits) with
`TODO(owner, FR-07)` on provisional values. Load it through the policy bundle with a schema.

Two resolvers for `UNSURE`:

- **Regex mode:** resolve `UNSURE` with the current heuristics, so that `split_sentences` keeps
  its present output. All existing splitter tests must pass unchanged, except tests that encode
  a known bug fixed by a SPLIT/NO_SPLIT rule; change those only with a comment naming the rule.
- **spaCy mode:** before the parser runs, set `token.is_sent_start` on the token starting at each
  candidate offset: `True` for SPLIT, `False` for NO_SPLIT, unset (`None`) for UNSURE; set `False`
  on every token that does not start at a candidate offset. The parser then decides only UNSURE.
  If a candidate offset does not align with a token start, record it as a counted alignment miss
  (no text logged) and treat it as NO_SPLIT.

Replace the spike's `_SentenceRules` component and abbreviation guard with this mechanism, so
there is one rule implementation for both modes.

Each sentence records how its starting boundary was decided: `rule:<rule id>` or `parser`.

## 5. Engine selection

- Add a setting `NLP_ENGINE` with values `regex` (default) and `spacy`, plus `NLP_MODEL`
  (default `en_core_web_sm`). Document both in `README.md` and `.env.example`.
- `regex` keeps today's behaviour and stores no token features. This keeps `make test` and the
  default dev setup working without the `nlp` extra.
- `spacy` with spaCy or the model missing must **fail the ingest job with a clear error**. Never
  fall back silently to regex.
- Load the spaCy engine once per worker process, not per article.

## 6. Storage

- Migration: add to `sentences`
  - `nlp_features JSONB NULL`: compact token arrays from `features.py` (schema version inside);
  - `boundary_source TEXT NULL`: `rule:<id>` or `parser`.
- Add to `articles` (or the ingest record if one exists) `nlp_engine JSONB NULL` holding
  `NlpEngineInfo` for the last ingest. Regex ingests store `{"engine": "regex", ...}` with the
  rules policy version so every article states how it was split.
- Migration heads: `dev` currently ends at `0008_merge_heads`; the vocabulary work on another
  branch adds `0007_vocabulary` and `0009_merge_vocabulary`. Run `alembic heads` at implementation
  time, create the new revision on the current head, and say in the report whether a merge
  revision will be needed when the branches meet.
- Token text is never stored; it is recovered from `sentences.text` and offsets.
- `reingest_article` uses the same path, so re-ingest with a new engine rewrites sentences,
  features, `boundary_source` and `nlp_engine` together in one transaction.

## 7. Mining receives features (no behaviour change)

- Add `tokens: tuple[TokenFeature, ...] | None = None` to `MiningItem`.
- The mine handler loads `nlp_features` with each sentence and passes it through. No stage uses it
  yet; candidate output for the same input must be byte-identical with and without features.
- Mining must not import spaCy.

## 8. Tests

Unit (no spaCy needed):

- `boundary_candidates` on all 24 dev fixture cases plus one case per rule row in section 4,
  asserting decision and rule id.
- Regex mode: existing splitter tests unchanged (see section 4 exception).
- Policy schema for `sentence_rules.yaml`.
- `MiningItem` with and without tokens gives identical candidates.

spaCy (`importorskip`):

- Hybrid mode on the 24 dev cases: **every case that the regex splitter or the round-2 web
  configuration got right must also be right in hybrid mode.** List any remaining failures in
  the report rather than tuning to them.
- Offset invariant, one ROOT per sentence, heads inside sentence (reuse spike tests).
- No token starts a sentence outside a candidate offset.

Integration (PostgreSQL, `TEST_DATABASE_URL` → `aprkb_test`):

- Upload → ingest with `NLP_ENGINE=regex`: `nlp_features` is null, `nlp_engine.engine == "regex"`.
- Ingest with `NLP_ENGINE=spacy` (skip if spaCy missing): features stored, offsets valid against
  `sentences.text`, mine job runs and produces the same candidates as regex for the same sentences.
- `NLP_ENGINE=spacy` without spaCy installed: the ingest job fails with a clear error.

## 9. Done when

- Docs in section 3 updated; ADR-0010 added.
- `make lint` and `make test` pass without spaCy; NLP and integration tests pass with spaCy in a
  dedicated venv (document the commands as in the round-2 report).
- If PostgreSQL is unavailable, list exactly which integration tests were not run.
- Report `plans/reports/YYMMDD-spacy-phase2-report.md`: dev-fixture results for regex, spaCy-only
  (round 2) and hybrid; count of boundaries decided by each rule and by the parser on the
  fixtures; alignment misses; migration notes; storage per sentence; open items for phase 3.
