# Phrasebank and recommendation delivery

Branch: `feat/phrasebank-and-recommend`. Base: `origin/dev` at `f032029`.

## Changes

- Carry move through retrieval/read models, API pattern responses and Writer links/context; score explicit intent or same-move matches.
- Add deterministic lexical MMR after gates/sort, configurable diversity policy, fallback trace, normalized explanation details and scorer ablation.
- Share conservative keyword normalization between online retrieval and linguistic scoring.
- Preserve the latest upstream journal-specific Phrasebank retrieval, retrieval grouping optimization and sentence-level Writer validation scope.
- Fix sidebar tooltip Escape interception and forward the account trigger ref for correct popup placement. Make Library/Journals/Inbox/Playground grids responsive.
- Add boundary, negative, recovery, keyboard, responsive, determinism and seeded invariant tests. The external link checker distinguishes robot-policy blocking from broken links.

## Validation and limits

**CI: not tested/verified for this delivery. Local tests do not establish CI success.** No workflow or CI configuration changes are included.

Local delivery validation: **693 backend unit/API tests passed, 1 upstream expected failure; 111 distinct browser tests passed after targeted rechecks. Ruff, format, mypy, frontend build/ESLint and generated OpenAPI checks passed.** Initial isolated-checkout DB credentials were corrected process-locally; two assertions were updated for upstream SQL prefiltering and contextual Writer links. The final results count each test once using its latest execution. Earlier mixed-workspace test totals are not reused as results for this branch. Publication and retry-job changes remain outside this branch, and tests for those unavailable routes are not included here.

Intent weight0.10 and same_move0.70 remain provisional policy values with owner TODOs. No embedding or automatic tier refill is introduced. Four Wikimedia pages return403 robot-policy responses to the local automated checker; this is inconclusive reachability, not a passed link check. Existing backend acceptance placeholders and the upstream expected-failure test are not silently treated as passing.

Raw browser traces, keys, database credentials, video, screenshots, caches and generated test-result directories are excluded from Git. The original development checkout is preserved separately.

## Local reproduction

Use a PostgreSQL `aprkb_test` database and process-local `TEST_DATABASE_URL` for backend integration tests; never copy secrets into the checkout. Run backend pytest/Ruff/mypy and frontend build/lint with the repository's configured toolchain.

For browser tests, `scripts/manual/online_ranking_live_server.py` migrates/seeds a disposable schema on port8016 and drops it on graceful shutdown. Run Vite against that API, set `ONLINE_RANKING_LIVE=1`, `WRITER_E2E_BASE_URL` and optionally `WRITER_E2E_BROWSER=msedge`, then run `playwright test --config=playwright.full.config.ts`. The API fixture uses packaged policies without test-only ranking overrides.
