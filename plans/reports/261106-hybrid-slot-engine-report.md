# Hybrid Slot Engine implementation report

Date: 2026-11-06  
Worktree: `D:\6_OJT\aprkb-spacy-spike`  
Branch/base: `feat/spacy-nlp-spike` / `21299c4fcfe3db6609f2e981599202a4f226fab3`

## Outcome

Implemented the Tier 2 fallback (seven families, then eight; see the last section) behind `MINING_HYBRID_ENABLED=false` by default.
Tier 1 stays authoritative; Tier 2 is reached only after reporting and construction misses and when
usable stored token features exist. The hybrid stage consumes stored tokens and does not load
spaCy. No storage migration was needed.

Added a separate provisional policy, source-offset frame construction, Frame Invariant and Purity
Gate checks, tense/ownership/fingerprint metadata, family and policy identity in clustering,
candidate writer support, and hybrid-frame checks in review and extraction. Added the hash-only
coverage CLI and an open-world scope ADR. Existing Tier 1 policy YAML and matching logic were not
changed.

## Phase 0 baseline

The worktree was on the requested branch and base. Existing user changes remained present in
`gold_labeling.yaml`, the two gold guideline files, and `plans/spacy-nlp-spike/verb-queue-spec.md`;
they were not edited by this work. `plan.md` and `spec.md` were copied into this worktree.

Commands run from `apps/backend` before implementation:

- `python -m ruff check .` — passed.
- `python -m ruff format --check .` — 307 files formatted.
- `python -m mypy` — 201 source files checked, no issues.
- Unit suite with `NLP_ENGINE=regex`, pytest basetemp under `%TEMP%` — 633 passed, 1 skipped.
- Unit suite in `tmp/phase3-spacy-venv` with `NLP_ENGINE=spacy`, pytest basetemp under `%TEMP%` — 645 passed.

The first test invocation used a nonexistent temp parent and failed during pytest setup; rerunning
with the actual `%TEMP%` location passed. This was a command setup issue, not a repository failure.

## Implementation and verification

- Added 43 self-authored hybrid fixture sentences (three positive and three negative per family,
  plus one additional Meta-NP case). Snapshot regeneration preserved the original 142 records
  exactly by parsed record comparison.
- Hybrid family suite — 45 passed. It checks family matches/rejections, required example frames,
  source-offset reconstruction, candidate writer acceptance, review/extraction safety gates, and
  Tier 1 precedence and fallback control flow.
- Final unit suite, regex — 678 passed, 1 skipped.
- Final unit suite, spaCy 3.8.18 venv — 690 passed.
- `ruff check .` — passed.
- `ruff format --check .` — passed (310 files formatted).
- `mypy` — passed (202 source files).
- `mining_coverage_report.py --help` — passed.
- `git diff --check` — passed.

The existing tests emitted the same environment warnings for the deprecated Starlette/httpx
combination, a Pydantic field shadow, and pytest cache writes denied under the read-only workspace
policy. They did not fail the suites.

## Coverage by family

There was no Tier 2 corpus baseline before implementation, so pre-change hybrid family coverage is
zero by definition. The post-change family fixture results are measured below. Rights-checked real
corpus output is **not measured**; see “Checks not run.”

| Family | Corpus before | Corpus after (first run) | Corpus after (fix round 1) | Authored positives passing | Authored negatives passing |
|---|---:|---:|---:|---:|---:|
| Passive academic | 0 | 354 | 704 | 3/3 | 3/3 |
| Extraposed `it` | 0 | 43 | 72 | 3/3 | 3/3 |
| Copular/definitional | 0 | 329 | 98 | 3/3 | 3/3 |
| Discourse gap | 0 | 156 | 126 | 3/3 | 3/3 |
| Participial lead-in | 0 | 78 | 61 | 3/3 | 3/3 |
| Comparative/correlation | 0 | 241 | 208 | 3/3 | 3/3 |
| Reporting-spine | 0 | 5 | 4 | 3/3 | 3/3 |

Corpus counts are Tier 2 extractions on the 51-article set (see "Corpus run and fix round 1").

The 90% frame correctness and 80% usefulness goals were not evaluated; they remain future goals.

## Checks not run

- PostgreSQL integration was run later; see "Integration run" at the end.
- The corpus baseline, hybrid-off/on runs and fix round 1 were run later; see the next section.
- `MINING_HYBRID_ENABLED=false` is now present in the root `.env.example`; this item is closed.

To run the remaining coverage checks when the approved corpus path and test URL are available:

```powershell
python scripts/mining_coverage_report.py <51-blob-directory> `
  --blob-root <blob-root> `
  --database-url <aprkb_test-url-on-port-55433> `
  --hybrid off --output plans/hybrid-slot-engine/tier1-baseline.jsonl

python scripts/mining_coverage_report.py <51-blob-directory> `
  --blob-root <blob-root> `
  --database-url <aprkb_test-url-on-port-55433> `
  --hybrid off --baseline plans/hybrid-slot-engine/tier1-baseline.jsonl `
  --output plans/hybrid-slot-engine/tier1-repeat.jsonl

python scripts/mining_coverage_report.py <51-blob-directory> `
  --blob-root <blob-root> `
  --database-url <aprkb_test-url-on-port-55433> `
  --hybrid on --baseline plans/hybrid-slot-engine/tier1-baseline.jsonl `
  --output plans/hybrid-slot-engine/hybrid-on.jsonl
```

The first two hybrid-off invocations form the deterministic repeat check; compare
`tier1-baseline.jsonl` and `tier1-repeat.jsonl` byte-for-byte. Manifests contain only SHA-256
identity/output hashes plus tier and family identifiers.

## Proposed `CLAUDE.md` wording

`CLAUDE.md` is owner-owned and was not edited. Proposed addition:

> The eight-family hybrid mining tier in ADR-0014 is a narrow, feature-flagged exception to
> general-purpose NLP extraction. It runs only after Tier 1 misses, consumes stored spaCy token
> features, and sends validated candidates to the existing pending review queue. Keep the switch
> disabled by default; do not add Tier 3, auto-approval, or general-purpose extraction.

## Resumed verification after the final patches

The earlier verification counts above predate the final Meta-NP relative-span, parsed-subject
ownership, and hybrid safety-key patches. These results are the fresh checks run after those
patches. The `.env.example` entry is present, so the earlier blocked-item note has been removed.

Commands run from `apps/backend` (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
$env:NLP_ENGINE='regex'; .\.venv\Scripts\python.exe -m pytest tests/unit --basetemp "$env:TEMP\hybrid-slot-engine-final-regex"
$env:NLP_ENGINE='spacy'; ..\..\tmp\phase3-spacy-venv\Scripts\python.exe -m pytest tests/unit --basetemp "$env:TEMP\hybrid-slot-engine-final-spacy"
git diff --check
```

Results:

- Ruff check passed; format check reported 310 files already formatted; mypy reported no issues
  in 202 source files; `git diff --check` passed.
- Regex unit suite: 680 passed, 1 skipped. spaCy venv unit suite: 692 passed.
- The requested 42 + 16 protected Tier 1 unit-test contract passed as part of both full suites.
  `slot_abstractor.py` has no diff from `21299c4`. The only `construction_matcher.py` change is
  the optional `ReportingWithConstruction` fallback; existing Tier 1 matching logic is unchanged.
- `constructions.yaml`, `slot_abstraction.yaml`, `construction_verb_groups.yaml`,
  `lexicon/lead_ins.yaml`, and `lexicon/reporting_verbs.yaml` have no diff from `21299c4`.
- Ruff initially found one overlong comment in `test_hybrid_slot_engine.py`; formatting that test
  fixed the issue, and all checks above were rerun. An initial mypy invocation through the global
  Python reported missing `openpyxl` stubs and unrelated repository errors; the project `.venv`
  invocation above passed.

## Plan section 7 checklist

| Done condition | Status | Evidence |
|---|---|---|
| 42 + 16 protected tests and full regex/spaCy unit suites pass | Met | Full suites: 680 passed, 1 skipped (regex); 692 passed (spaCy). |
| Hybrid-off baseline has zero differences; hybrid-on preserves Tier 1; both repeat identically | Not run | The 51-article corpus/baseline run is deferred to the owner; no corpus comparison was performed. |
| Each family has 3 positive and 3 negative fixtures, or a parse exception is documented | Met | All seven families have 3/3 authored positives and 3/3 negatives in the family fixture suite; full suites pass. |
| Every accepted Tier 2 candidate passes frame, purity, and metadata checks | Met | Hybrid unit suite passed, including validation and metadata assertions. |
| Candidate can be listed, opened, and approved through review | Not run | End-to-end review flow requires the deferred integration run; unit safety checks do not exercise persistence/list/open/approve. |
| Ruff, format check, and mypy pass | Met | Commands and results above. |
| Integration passes on `aprkb_test` in both engines, or exact skipped checks are reported | Not run | Integration was deferred per owner instruction; no database was accessed. |
| Report gives coverage before and after per family | Not met | Fixture coverage is reported above; corpus-after counts remain not measured because the corpus run is deferred. |

The 51-article corpus run, Tier 1 corpus baseline, integration tests, and all database access remain
owner-only work. Port `55432` was not used. No article text was added to this report.

## Corpus run and fix round 1 (counts only)

Input: 51 stored articles in one field. Rights came from a read-only export of blob key and licence
code for mining-allowed articles (all `DEV-UNVERIFIED`), passed with the new `--rights-file`
option, so the script opened no database connection. The set reproduces the Phase 8.1 totals:
29,344 sentences scanned, 12,178 kept. Licence status is still unverified, so these numbers
evaluate the algorithm and do not clear any phrase for use.

Tier 1 baseline: built from a clean `git archive` of `21299c4`, not from this working tree.

| Measure | Tier 1 only | Hybrid, first run | Hybrid, after fix round 1 |
|---|---:|---:|---:|
| Extractions | 363 | 1,569 | 1,636 |
| Tier 2 extractions | 0 | 1,206 | 1,273 |
| Distinct frames | 169 | 1,351 | 1,347 |
| Distinct cluster keys | 306 | 1,495 | 1,554 |
| Frames in 2 or more articles | 51 | 70 | 116 |
| Average literal words per Tier 2 frame | n/a | 17.8 | 5.6 |
| Differences against the Tier 1 baseline | 0 | 0 | 0 |

`--hybrid off` is byte-identical to the baseline. Two `--hybrid on` runs are byte-identical.

Most frequent errors found in the first run, and the fix for each:

| Error (first run) | Frames | Fix |
|---|---:|---|
| Frame kept the whole sentence, including lead and trailing clauses | 866 had over 10 literal words | Frame is now the pattern core of the main clause |
| Slot was only a pronoun or function word (`it`, `they`, `we`) | 87 | Reject by part of speech, no word list |
| Two clauses joined by `;` or `:`, stray bracket, unbalanced parenthesis | about 90 | Reject in the engine and in `is_safe_hybrid_frame` |
| Family trigger word fell outside the trimmed core | 329 attempts | Require the trigger inside the core |
| Core too short for the old 3-content-word minimum | 1,969 attempts | `min_content_tokens: 1`, still requires a verb, adjective or Meta-NP head |

Policy changes: `hybrid_constructions.yaml` is now v0.2.0, with `max_literal_words: 12` and
`min_content_tokens: 1`. The owner confirmed both on 2026-11-07, so they are standard
parameters and carry no `TODO(owner)`. No Tier 1 file changed.

Checks after round 1: ruff, format check and mypy pass. Unit suite: 686 passed, 1 skipped (regex);
698 passed (spaCy). `git diff --check` reports only the repository's existing CRLF notices.

Known remaining issues: 441 attempts fail the frame invariant (slot spans adjacent or invalid);
205 are rejected for a lead that is too long; proper-noun literals written in lower case pass the
Purity Gate because there is no word list. Quality has not been measured against a labelled set.

## Fix round 2 (counts only)

Round 2 targeted the 441 `frame_invariant` rejections. Diagnosis: 437 were overlapping slots, 343
of them in the passive family. The agent search walked the whole root subtree, including the
subject, so it could pick a phrase inside the subject. The comparison search had the same flaw
against both the subject and the direct object. Both searches now exclude those subtrees.

Review of the new frames found a second defect: a family trigger word (for example `less`) was
accepted even when it sat inside a slot, so `[X] can lead to [Y]` matched the comparative family.
Triggers are now searched in the literal text only. This removed false matches (comparative
256 to 114, discourse gap 126 to 74 on the 51 articles).

| Measure | Tier 1 only | After round 1 | After round 2 |
|---|---:|---:|---:|
| Extractions | 363 | 1,636 | 1,722 |
| Tier 2 extractions | 0 | 1,273 | 1,359 |
| Distinct frames | 169 | 1,347 | 1,390 |
| Distinct cluster keys | 306 | 1,554 | 1,639 |
| Frames in 2 or more articles | 51 | 116 | 124 |
| Differences against the Tier 1 baseline | 0 | 0 | 0 |

Tier 2 by family after round 2: passive 935, comparative 114, copular 99, discourse gap 74,
extraposed `it` 72, participial 61, reporting-spine 4. `--hybrid off` is byte-identical to the
baseline, and two `--hybrid on` runs are byte-identical. `frame_invariant` rejections fell from
441 to 26.

Net gain over round 1 is about 5% more extractions, so the plan's stopping rule applies: no round
3. Added two self-authored fixtures and tests for the two defects. Checks: ruff, format check and
mypy pass; unit suite 688 passed, 1 skipped (regex) and 700 passed (spaCy).

Largest remaining limit: about 10,300 kept sentences match no family. Covering them needs new
families or a more general clause family, which is a design decision for the owner.

## Eighth family: modified active clause (counts only)

Owner decision (2026-11-07): add `hybrid_active_modified` as the eighth Tier 2 family, with a
syntax-only rule and no verb list. The clause must be active, have a subject and a direct object,
no modal, and an adverb after the subject or a prepositional phrase after the object (the phrase's
object becomes slot `Z`). A prototype compared three variants on the 51 articles before the choice:

| Variant | New extractions | Frames in 2 or more articles |
|---|---:|---:|
| Modifier required, no verb list (chosen) | 637 | 33 |
| Modifier required, 8 light verbs excluded | 593 | 32 |
| Modifier required, 17-verb academic allowlist | 40 | 0 |

The owner also asked for a check on punctuation next to placeholders. Frames are now rejected
when punctuation, `-` or `/` touches the left of a placeholder, or a letter, digit, `-` or `/`
touches its right (a span cut inside a token). The check runs in the engine and in
`is_safe_hybrid_frame`, so review and extraction re-check it. Policy is now v0.3.0.

| Measure | Tier 1 only | After round 2 | With eighth family |
|---|---:|---:|---:|
| Extractions | 363 | 1,722 | 2,337 |
| Tier 2 extractions | 0 | 1,359 | 1,974 |
| Distinct frames | 169 | 1,390 | 1,963 |
| Distinct cluster keys | 306 | 1,639 | 2,242 |
| Frames in 2 or more articles | 51 | 124 | 154 |
| Share of the 12,178 kept sentences | 3.0% | 14.1% | 19.2% |
| Differences against the Tier 1 baseline | 0 | 0 | 0 |

New family: 630 extractions. `--hybrid off` is byte-identical to the baseline and two `--hybrid on`
runs are byte-identical. Added 6 self-authored fixtures (3 positive, 3 negative) and tests for
the family and the boundary check. Checks: ruff, format check and mypy pass; unit suite 696 passed,
1 skipped (regex) and 708 passed (spaCy).

About 94% of the new family's frames occur once. They rely on the pending review queue and on
document-frequency clustering to be filtered, as the owner chose.

## Integration run (aprkb_test, port 55433)

Run on 2026-11-07 against the dedicated `aprkb_test` database on port 55433 only; each run uses
its own schema. Port 55432 was not used.

| Engine mode | Command target | Result |
|---|---|---|
| `NLP_ENGINE=regex` | `pytest tests/integration` | 81 passed |
| `NLP_ENGINE=spacy` | `pytest tests/integration` | 81 passed |

Two new tests in `tests/integration/api/test_routes.py` cover the hybrid review path:

- A candidate written through the real `CandidateWriter` appears in the review queue, needs two
  approvals, and is promoted to a pattern version. The source licence is `DEV-UNVERIFIED`, and
  the evidence record keeps that licence id. The queue response does not contain source text.
- A hybrid candidate whose cluster key carries a stale policy version fails closed: the queue and
  the approve call both return 409, and no version is created.

Findings from reading the flow: the candidate table stores `cluster_key` but not
`construction_id`, so `is_safe_hybrid_frame` reads the family from the cluster key and requires
the current hybrid policy version. A later policy version bump makes pending hybrid candidates
unsafe, and the queue endpoint returns 409 for the whole queue, so clear or re-mine them first.
`DEV-UNVERIFIED` allows mining and display, so approval succeeds; the pack validator (E12)
refuses it on export. The recommendation path for this licence was not traced.

## AI-labelled quality check (counts only)

Sample: 99 distinct Tier 2 frames from the 51-article run, drawn with a fixed seed (20261107),
stratified by family and shuffled. `reporting_spine` has only 3 distinct frames, so it is
under-sampled. The labeller saw each frame and its slot texts, not whole sentences, and did not
see the family. The rubric was fixed before labelling:

- GOOD: a reusable academic writing pattern, sensible slots, no topic-specific literal words.
- WEAK: right structure, but too generic, truncated or awkward.
- BAD: broken slot boundary, wrong structure, or topic-specific words in the literal text.

This is one AI labeller and no human review yet, so treat it as a first estimate. With n=99 the
95% interval on a rate near 34% is about plus or minus 9 points.

| Family | n | GOOD | WEAK | BAD |
|---|---:|---:|---:|---:|
| passive_academic | 20 | 5 | 9 | 6 |
| active_modified | 20 | 6 | 11 | 3 |
| comparative_correlation | 12 | 4 | 4 | 4 |
| copular_definitional | 12 | 4 | 4 | 4 |
| discourse_gap | 12 | 1 | 1 | 10 |
| extraposed_it | 10 | 6 | 3 | 1 |
| participial_lead_in | 10 | 5 | 3 | 2 |
| reporting_spine | 3 | 3 | 0 | 0 |
| **All** | **99** | **34 (34%)** | **35** | **30** |

GOOD plus WEAK is 70%. The earlier targets (90% correct, 80% useful) are not met.

Why frames were not GOOD (65 frames): topic-specific literal words 34, too generic 13, wrong slot
boundary 11, truncated 4, not a pattern 3. Among the 30 BAD frames, 20 are topic-specific
literals. Frames seen in two or more places: 9 sampled, 5 GOOD (55%); frames seen once: 90
sampled, 29 GOOD (32%).

Reading: the Purity Gate has no word list, so ordinary topic nouns pass as literal text. That is
the main defect, and `discourse_gap` suffers most because its subject stays literal.

## Why frames were not good, and the decision on `discourse_gap` (counts only)

The same 99-frame sample was rebuilt from its seed and joined to the labels, with the literal
tokens of each frame recorded (part of speech, dependency role, position).

Where the topic words sit (34 frames labelled as containing topic-specific literal words): 16
noun occurrences are in a trailing prepositional phrase after the last slot, 9 are subjects left
literal, 9 are noun compounds attached to a slot, and 6 are objects between slots. The engine
decides literal versus slot by syntactic role only, so any noun that is not chosen as a slot
stays as literal text, and nothing checks that the literal words are pattern-like.

Number of literal content nouns (outside a short discourse lead and the Meta-NP heads):

| Label | 0 nouns | 1 noun | 2 or more |
|---|---:|---:|---:|
| GOOD (34) | 31 | 3 | 0 |
| WEAK (35) | 24 | 3 | 8 |
| BAD (30) | 7 | 10 | 13 |

Candidate list-free filters, simulated on the labelled sample (not applied):

| Rule | BAD removed | WEAK removed | GOOD lost | GOOD share of what is kept | Frames removed overall |
|---|---:|---:|---:|---:|---:|
| Reject at 1 or more literal content nouns | 23 of 30 | 11 of 35 | 3 of 34 | 50% (n=62) | 417 of 1,797 |
| Reject at 2 or more | 13 of 30 | 8 of 35 | 0 of 34 | 44% (n=78) | 175 of 1,797 |
| Reject nouns that are subject or object | 17 of 30 | 3 of 35 | 1 of 34 | 42% (n=78) | 216 of 1,797 |

The first rule is the strongest. The 3 GOOD frames it would lose carry ordinary function nouns
(`terms`, `space`, `benchmark`). Of the 7 BAD frames it would keep, 4 are truncated or have wrong
slots, and 3 have topic words that are not nouns.

Decision (owner, 2026-11-07): `hybrid_discourse_gap` is disabled (1 GOOD of 12 sampled). The
policy has a new `enabled` flag, so the family logic and its tests stay. Policy is now v0.4.0, and
a disabled family is also rejected by `is_safe_hybrid_frame`.

| Measure | With 8 families | `discourse_gap` disabled |
|---|---:|---:|
| Extractions | 2,337 | 2,289 |
| Tier 2 extractions | 1,974 | 1,926 |
| Distinct frames | 1,963 | 1,911 |
| Frames in 2 or more articles | 154 | 155 |
| Differences against the Tier 1 baseline | 0 | 0 |

The literal-noun rule is not applied yet and needs an owner decision. Checks: ruff, format and
mypy pass; unit suite 697 passed, 1 skipped (regex) and 709 passed (spaCy); the two hybrid
integration tests pass on `aprkb_test`.


## Frame cleanup, policy v0.5.0 (2026-11-07)

The owner reviewed the exported frames and reported four problems. Checking them against the data
changed two of them.

- **Recurrence was overstated.** One article is stored as two blobs with two DOIs, so 17 frames
  counted as recurring came from a single article. The corpus is 50 articles, not 51. The report
  now takes `--article-ids` and counts canonical frames per article.
- **The "null" slot was an export bug.** The cell text began with `=`, so the spreadsheet read it as
  a formula. The real defect was formula text inside slots.

Changes, all hybrid-only:

- The final period is removed from `canonical_skeleton`, so it no longer splits clusters. The
  displayed frame keeps it. Case was already folded by the clusterer.
- Trailing prepositions are cut back in `_core_range`. Anything left is rejected.
- New gates reject formula slots, side-remark abbreviations, and punctuation set off by a space.
- `is_safe_hybrid_frame` applies the same frame checks, so stored frames fail closed.

| Measure | v0.4.0 | v0.5.0 |
|---|---:|---:|
| Extractions | 2,289 | 2,204 |
| Tier 2 extractions | 1,926 | 1,841 |
| Tier 2 canonical frames | 1,666 | 1,585 |
| Tier 2 frames in 2 or more articles | 109 (6.5%) | 110 (6.9%) |
| Tier 1 frames in 2 or more articles | 52 | 52 |
| Differences against the Tier 1 baseline | 0 | 0 |

The literal-noun rule is still not applied. Two runs are byte-identical. Checks: ruff and mypy pass;
unit 714 passed, 1 skipped (regex) and 726 passed (spaCy); integration 81 passed in each mode.

## One candidate per cluster, policy v0.6.0 (2026-11-07)

Every mined sentence used to become its own candidate row, so one frame could fill the review queue
many times. The cluster key was only a label. Owner decision: upsert per cluster and append sources.

- `candidates.cluster_key` is now unique (migration `0012_candidate_cluster_unique`). The migration
  stops if keys already repeat; it does not merge reviewed rows. The real database has no repeats.
- The worker upserts in sorted key order, so two mining jobs cannot deadlock on the same clusters.
  A sentence already listed is skipped, so repeat mining adds nothing.
- A reviewed cluster keeps its status when a source is added. Accepted clusters are not reviewed
  again. Rejected clusters stay rejected for every later article.
- Occurrence count is the length of `source_sentence_ids`, shown as `occurrence_count` in the
  review queue. No counter, DOI or licence copy is stored: readers join to the current licence.
- `reingest_article` removes only that article's sources from a shared pending cluster. Any
  reviewed cluster still blocks re-ingest, and this now reaches every contributing article.
- Tier 2 no longer puts slot text in the key. Tier 1 reporting followed later; see the next section.

Hybrid stays off by default.

| Measure | v0.5.0 | v0.6.0 |
|---|---:|---:|
| Extractions | 2,204 | 2,204 |
| Cluster keys (review items) | 2,112 | 1,915 |
| Distinct frames | 1,829 | 1,829 |
| Differences against the Tier 1 baseline | 0 | 0 |

Two runs are byte-identical. Checks: ruff and mypy pass; unit 714 passed, 1 skipped (regex) and 726
passed (spaCy); integration 85 passed in each mode.

## Slot text removed from Tier 1 reporting keys (2026-11-07)

Owner decision: the reporting key no longer holds slot text, and `slot_binding_fingerprint` is
gone. This supersedes the earlier "verbatim-only consolidation" choice, which existed to keep each
occurrence's slots. Candidates now keep every occurrence, so that protection is no longer needed.

Keys still use the reporting verb class. On this corpus, all 7 merged groups were singular and
plural forms of one verb, such as `show` and `shows`; no synonyms mixed. Tense, strength and
ownership still split clusters.

| Measure | Before | After |
|---|---:|---:|
| Tier 1 reporting keys | 200 | 67 |
| Tier 1 keys | 306 | 173 |
| All keys (review items) | 1,915 | 1,782 |
| Tier 1 rows with changed content | n/a | 0 of 363 |

Tier 1 content was compared with a clean baseline, leaving the key out of the hash, because the key
recipe changed on purpose. Keyed runs are byte-identical. Existing candidates keep their old keys,
so mining those articles again adds new rows beside them. Checks: ruff and mypy pass; unit 714
passed, 1 skipped (regex) and 726 passed (spaCy); integration 85 passed in each mode.

## Literal-noun gate and slot order, policy v0.7.0 (2026-11-07)

- New gate `purity_literal_noun` (`max_literal_nouns: 0`): a frame is rejected when literal text keeps a
  noun that is not a Meta-NP head. Owner review of 30 frames: it removed 13 BAD and 2 WEAK, no GOOD.
- Slots are now named in reading order, so a fronted phrase is `[X]`, never `In [Y], [X] ...`. Before
  this, 175 of 1,841 Tier 2 rows (41 articles) failed `is_safe_hybrid_frame`; with hybrid on, the
  candidate writer would have failed those articles' mining jobs.
- The coverage report now counts `unsafe_hybrid_frames`; it must stay 0.
- 50 articles: Tier 2 canonical frames 1,585 to 1,258, recurring in 2+ articles 110 to 104, unsafe 0.
  Tier 1 unchanged (164 frames, 52 recurring). Runs are byte-identical.
- Open: fixed leads mis-slotted (`For example`), heading glued to a sentence, cut compounds. About
  29 of 31 WEAK frames in the sample stay too generic.

## Frame-quality gates, policy v0.8.0 (2026-11-07)

- Fixed leads from `lexicon/lead_ins.yaml` stay outside slots. Policy v0.2.0 adds `For example` and
  `In contrast`; the passive-method matcher skips configured leads when searching for a method
  phrase, and a lead selected as a slot is rejected.
- Modifier dependencies may not cross a slot edge, so compounds and modifiers stay with their head.
- Heading joins are rejected at the hybrid frame gate when a capitalized sentence-initial function
  word appears after the first slot. This leaves shared sentence segmentation unchanged and keeps the
  rejection local to hybrid candidates.
- The provisional `min_fixed_content_tokens: 2` gate requires two fixed content words outside slots.
  It is vocabulary-free and carries `TODO(owner, FR-06.2)` pending owner review.
- On the 63 self-authored hybrid fixtures, changing only that threshold from 1 to 2 reduced accepted
  fixtures from 36 to 28 (8 fewer); all 190 pre-existing token snapshot records are unchanged, and
  the writer-safety check runs before the engine returns a frame.
- The prior 50-article v0.7.0 run measured 1,258 Tier 2 canonical frames, 104 recurring in at least
  two articles, and zero unsafe frames. The licensed 51-blob input set and rights map are not present
  in this workspace, so a comparable v0.8.0 corpus run could not be measured here.
- Open: assess the threshold against a refreshed labeled sample (including the reported 31 WEAK
  frames) and rerun the 50-article coverage comparison when its rights-checked inputs are available.

## Threshold back to 1, policy v0.8.1 (2026-11-07)

- Measured on 50 articles: `min_fixed_content_tokens: 2` cut Tier 2 extractions 1,874 to 1,000, frames
  1,258 to 593, and recurring frames 104 to 21. In the owner's 30-frame sample it lost 7 of 11 GOOD
  frames; on the 100-frame AI-labelled sample GOOD share moved only 57% to 59% while 19 GOOD were lost.
- v0.8.1 sets the threshold to 1: extractions 1,863, frames 1,255, recurring 102, unsafe frames 0,
  two runs byte-identical, Tier 1 unchanged (0 differences on 363 content rows).
- Owner read of a fresh 30-frame random sample at v0.8.1: 26 GOOD, 2 WEAK, 2 BAD (93.3% usable).
- Hedging and limitation survey (50 articles, read-only): no new branch met the volume gate, so no
  new family or branch was added. Open: 21 of 32 extracted modal sentences have the modal outside the
  frame, so `epistemic_tagger` cannot see it; not investigated yet.
