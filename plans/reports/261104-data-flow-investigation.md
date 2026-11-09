# Data flow investigation

Date: 2026-11-04 (Asia/Bangkok)
Scope: source-code investigation of the current checkout. No pipeline, database, or deployment changes. External scraper code, production processes, and deployed database contents were not inspected. The proposed `data_innit` file does not exist yet.

## Main finding

The repository already has multiple explicit intermediates and entry points. They represent different data stages, not necessarily duplicate imports. The strongest existing file handoff is the approved-pattern data pack. A single file name will not by itself resolve mixed frontend data sources, different approval meanings, or multiple writers sharing a database configuration.

## Current routes from source to app

| Input / action | Intermediate | Database destination | Consumer |
|---|---|---|---|
| Manual article upload | Stored source blob and ingest job | `articles`, then `article_sections` and `sentences` | Mining/review and article views |
| SLR remote import | Typed `SourceArticleRef` / `SourcePage`, downloaded blob and jobs | Same article and sentence tables | Same downstream mining pipeline |
| Mining | Typed mining items through stages | Pending `candidates` | Two review workflows |
| Two-round review with assigned intent | Candidate decisions | `phrase_patterns`, `pattern_versions`, usage and provenance | Real Writer and AP-RKB Phrasebank |
| One-reviewer acceptance in `/extract` | Candidate decision | Separate `approved_phrases` store | Extraction workflow; no automatic Writer publication |
| Offline pattern export | `manifest.json` plus `patterns.json` | Validated pack import into destination pattern tables | Real Writer and AP-RKB Phrasebank |
| Scraped Manchester collection JSON | Parsed collection plus taxonomy mapping inputs | Separate `reference_*` tables | Manchester source in Phrasebank |
| Development seed files and policy YAML | Seed loader | Reference data and sample patterns | Backend reads of seeded data |
| Curator pattern API | Validated request | Draft pattern / new version | Pattern management and later eligibility checks |
| Frontend prototype constants | In-memory mock API | None | `/library`, `/playground`, and other prototype pages |

Evidence: [corpus service](../../apps/backend/src/aprkb/modules/corpus/service.py), [corpus importer](../../apps/backend/src/aprkb/modules/corpus/importer.py), [worker handlers](../../apps/backend/src/aprkb/worker/handlers.py), [review service](../../apps/backend/src/aprkb/modules/review/service.py), [extraction service](../../apps/backend/src/aprkb/modules/extraction/service.py), [pack service](../../apps/backend/src/aprkb/modules/pack/service.py), [reference importer](../../apps/backend/src/aprkb/modules/reference_library/importer.py), [seed loader](../../apps/backend/src/aprkb/seeds/load.py), [pattern service](../../apps/backend/src/aprkb/modules/patterns/service.py), [mock API](../../apps/web/src/shared/api/index.ts).

## Concrete sources of confusion

### 1. Some pages do not read the database

The router sends `/library` to a component importing `api` from `shared/api/index.ts`; that module filters in-memory `PATTERNS` from mock files. `/playground` uses the same prototype API. `/writer` and `/phrasebank` use real backend APIs. Updating an imported file or database therefore cannot update every screen.

References: [router](../../apps/web/src/app/router.tsx), [Library page](../../apps/web/src/features/library/components/LibraryPage.tsx), [mock API](../../apps/web/src/shared/api/index.ts), [Phrasebank sources](../../apps/web/src/features/phrasebank/source-registry.ts).

### 2. Accepted extraction phrases are not published patterns

The two review routes consume the same pending candidate pool. Two-round review requires an intent and creates an approved pattern. `/extract` acceptance creates an `ApprovedPhrase`, then marks the candidate accepted; normal review will no longer accept that candidate because it requires pending status. This is a real business/lifecycle distinction. A universal JSON schema would need to preserve it, rather than treating all accepted items as ready for Writer.

References: [review decisions and promotion](../../apps/backend/src/aprkb/modules/review/service.py), [extraction decisions](../../apps/backend/src/aprkb/modules/extraction/service.py).

### 3. Manchester content has a second, independent mapping input

`import-reference-library --file` explicitly reads the collection JSON. Its importer also uses checked-in `taxonomy-mapping.yaml` to initialize missing mappings. A separate `import-reference-mapping --file` command loads reviewed YAML mappings. Reimport replaces entry rows, preserves categories by slug, and removes stale mappings when heading/category titles change. The collection JSON alone cannot reproduce all reviewed mapping state.

These are concrete extra data inputs worth documenting. The inspected importer is command-driven; it does not watch the JSON for changes. No evidence was found in these paths of an automatic hidden file hook. This does not rule out external scripts or deployment jobs outside the inspected checkout.

References: [reference importer](../../apps/backend/src/aprkb/modules/reference_library/importer.py), [mapping importer](../../apps/backend/src/aprkb/modules/reference_library/mapping.py), [CLI](../../apps/backend/src/aprkb/cli.py).

### 4. A suitable approved-knowledge intermediate already exists

The pack has a strict versioned schema, producer/taxonomy metadata, stable pattern/version IDs, file checksums, counts, validation, dry-run import, append-only version checks, and repeat-import handling. Export validates each pattern graph and reports exclusions. It deliberately excludes raw article text and the separate extraction phrase store.

Some internally approved patterns still fail export requirements: native mined promotion leaves claim type unknown, while the pack requires valid labels. This is a missing enrichment transition, not an import hook. Move classification and dedup matching also remain pass-through TODO stages in mining.

References: [pack contract](../../doc/data-pack-spec.md), [pack models](../../apps/backend/src/aprkb/modules/pack/models.py), [pack validator](../../apps/backend/src/aprkb/modules/pack/validator.py), [pack service](../../apps/backend/src/aprkb/modules/pack/service.py), [mining registry](../../apps/backend/src/aprkb/modules/mining/stages/__init__.py).

### 5. Multiple writers are possible against the configured database

API, worker, seed loader, and import/export CLI commands build connections from `settings.database_url`. Separate deployments can supply separate values, but the shared modules do not enforce an Offline/Online boundary. A file-only publication rule is therefore not technically mandatory today.

Full development seeding is also a content writer: rerunning it updates seeded pattern intent/status and can restore a seeded pattern that was retired. `init-reference` intentionally initializes reference data without sample patterns. Source identity rules differ too: SLR import checks duplicate external IDs/DOIs before fetching, whereas manual upload creates a fresh article.

References: [app startup](../../apps/backend/src/aprkb/api/main.py), [worker](../../apps/backend/src/aprkb/worker/runner.py), [CLI](../../apps/backend/src/aprkb/cli.py), [seed loader](../../apps/backend/src/aprkb/seeds/load.py), [corpus importer](../../apps/backend/src/aprkb/modules/corpus/importer.py).

## Suggested direction for discussion

Start by standardizing the **handoff into usable app knowledge**, using the existing pattern pack. Producers may acquire and review data differently, but publish a common validated artifact. The app continues reading its database through the API; it should not need to read a mutable JSON file on every request.

```text
Acquisition → source storage / staging DB → processing and review
                                            ↓
                              versioned validated release artifact
                                            ↓
                                 controlled destination importer
                                            ↓
                                    app DB → API → UI
```

If the team wants one delivery unit, consider one release directory or archive with a manifest referencing typed files. Reuse the existing `patterns.json` contract for approved patterns. Keep scraped reference collections and their reviewed mappings distinguishable. Add a new contract version if the release must carry additional datasets; the existing v0.1 manifest permits only `patterns.json`.

Raw article blobs, jobs, reviews, audit logs, and Writer feedback have different purposes and do not all need to round-trip through this artifact. Policy YAML and taxonomy prerequisites must still be versioned or recorded for reproducibility. Runtime recommendation logs and feedback remain legitimate writes even if published knowledge is managed through releases.

A practical first step is to document each dataset's owner, producer, importer, destination, approval state, update/duplicate rules, and consuming pages. Then decide whether the first standardization target is (a) scraped reference ingestion or (b) approved Offline-to-app publication. The code currently supports (b) much more directly.

## What remains undecided

Decision update: the user clarified that only Phrasebank and its filters are in scope, covering both Manchester and AP-RKB sources. The implementation uses one path manifest to coordinate the existing pattern pack, reference collection, and reviewed mappings in one transaction. See `doc/phrasebank-initialization.md` and `plans/existing-pack-adoption/spec.md`. A universal content format, exclusive publication enforcement, and broader data migration are out of scope. The questions below remain future considerations rather than blockers.

- Which dataset and lifecycle boundary the team wants to standardize first.
- Whether `/extract` acceptance should eventually lead to Writer publication, and what additional review/labels it requires.
- Whether the desired result is reproducible transfers, one importer command, or enforced separation of publishing credentials. These are separate outcomes.

This investigation supports the approved reuse direction. No new JSON format, data migration, or runtime consolidation has been implemented.

## Risk and effort assessment

Assessed from the current source; these are engineering judgments, not measured delivery estimates or a production-data migration audit.

| Scope | Relative effort / risk | Effect on existing flow |
|---|---|---|
| Document and consistently use the current approved-pattern pack | Small to moderate / low to moderate | Can leave acquisition, mining, reviews, existing DB reads, and UI unchanged; changes how new knowledge is delivered |
| Make that pack the exclusive publishing route | Moderate / moderate | Requires control over other content writers, separate publishing credentials or deployment modes, and an explicit release/withdrawal process |
| Package Manchester content and reviewed mappings reproducibly | Moderate / moderate | Needs a versioned contract extension or separate typed package, identity/update rules, and mapping preservation tests |
| Force every dataset and workflow through one universal mutable JSON | Large / high | Changes uploads, background jobs, review transitions, seeds, reference import, and operational writes; creates substantial coupling and migration work |

### Important concrete risks

1. **Missing withdrawals.** Pack validation only permits approved patterns (`validator.py:156`); export skips non-approved patterns (`pack/service.py:459`); import adds supplied rows without reconciling omitted pattern IDs (`service.py:319`). Consequently, retiring a source pattern and exporting again does not itself retire its already imported destination copy. This follows from the inspected implementation; no live database experiment was performed. Define explicit retirement/revocation records or a carefully scoped authoritative snapshot before making this the exclusive publication route. Never equate an omitted item with deletion without first defining dataset ownership and export exclusions.
2. **Rollback is not just reimporting an older pack.** Imports reject missing stored versions (E16) and changed stored content (E15), and unchanged packs return without moving the current-version pointer. A release rollback needs a defined activation/history mechanism or verified database restore procedure. Transaction rollback protects a failed import, not reversal of a successful release.
3. **Existing data may be valid locally but fail the transfer contract.** Unlabelled mined claims, missing reviews/provenance, taxonomy mismatch, or unsupported metadata can exclude records. Produce an export reconciliation report before cutover; compare eligible/exported/excluded IDs and reasons. Do not clear the current database and rebuild it from the first successful JSON export.
4. **Mapping and identity loss.** Manchester reimport currently replaces entry rows; reviewed mappings are another input. A new importer must preserve their meaning or explicitly migrate them. Preserve stable pattern/version IDs to avoid duplicate knowledge and broken historical references.
5. **Two sources of truth.** A hand-edited JSON and directly edited destination database can diverge. Decide who owns published knowledge and which writes are permitted. One filename does not enforce that decision. Runtime logs/feedback should remain separate from published content ownership.
6. **Coupling and performance.** A universal file makes unrelated entity changes share a schema and release cycle. Large articles belong in blob storage; copying them into one repeatedly parsed JSON adds avoidable size and processing work. A typed release manifest allows independent payloads and later adapters.

### Safe incremental adoption

1. Keep the current database and runtime API as they are. Inventory content writers and compare mock versus real pages.
2. Export a snapshot to a new artifact; validate and dry-run it against an isolated destination. Record exported/excluded records and check repeat-import behavior.
3. Compare the destination's API-visible knowledge against the source. Include taxonomy mappings, provenance, approval state, and the newly fixed filter/license behavior.
4. Define retirement, correction, and rollback semantics before making releases authoritative. Specify who may publish versus edit staging data.
5. Switch only new approved-pattern publication to the agreed route. Migrate existing records only with a separate reconciliation and recovery plan. Broaden to reference collections after the first boundary works.

### Expected future value and limits

A standard release contract can improve repeatable imports, debugging, test fixtures, team handoffs, provenance traceability, environment setup, and support for additional scraping sources. These benefits come from validation, stable identity, versioning, and ownership rules; JSON is merely one serialization choice. A new source can adapt to an existing contract while the consumer remains stable.

It will not implement deduplication, fix absent labels or review transitions, convert mock pages to real API pages, or automatically improve Writer recommendation quality. Benefits are strongest at a clear publication boundary; forcing ordinary runtime processing through files would add work without solving those gaps.
