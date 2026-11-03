# UI redesign: final report (Phase 06)

Branch `feat/ui-redesign`. Desktop web only (1440px). Playwright not run (owner decision). Decisions are recorded in `doc/adr/0011-frontend-design-system.md`.

## What was removed

- `apps/web/src/app/styles.css` (legacy stylesheet) and `apps/web/src/shared/ui/*` (legacy primitives). The few global rules the app still needs (body size, link colour, skip link, `.main` container, `--shell-top`) now live in `globals.css`. The router's loading state uses `DataState`.
- `package-lock.json` (pnpm only) and the temporary sidebar shell, earlier in the branch.

## Verification

| Check | Result |
|---|---|
| `pnpm typecheck`, `pnpm lint`, `pnpm build` | Pass. Lint: 0 errors, 1 old warning (`OnlineWriterPage.tsx` effect dependency). |
| Production bundle | No `dev/ui`, no `demo-session`. Main chunk 711 kB (about 18 kB CSS gzip, `index`), landing chunk 20 kB, separate. The main chunk is above Vite's 500 kB hint: routes are not code-split yet. |
| `lint.mjs --app` (taste) | 0 FAIL on the new and changed screens. |
| `inspect.mjs --app --widths 1440`, 12 staff screens | 0 FAIL on all. WARN: app 2, vocabulary 0, library 2, phrasebank 1, journals 4, inbox 2, gold 4, extract 1, import 1, admin 2, playground 2, writer 0. Landing: 0 FAIL, 1 WARN (serif slot in the headline). WARN are layout notes (empty states, unequal column heights, monospace for IDs and slots). |
| Teal budget (script, every staff screen) | At most one primary button per screen (0 or 1). No other element has a teal background except buttons, selected toggles and radios. |
| Dark theme | Checked on Library: neutral black, `#5fb4cc` accent, readable. |
| Contrast | The inspector reports no contrast WARN on the staff screens; measured pairs for teal are in `plan.md` (white on teal 5.94:1, slot ink 7.28:1, `#5fb4cc` on near-black 8.38:1). Navigation shows the active item with a grey pill and an icon, not by colour alone. |
| Writer flow (CDP script) | Search, pick, fill slots, build, validate, copy: exactly one primary button at each step. |
| Guards (CDP script) | `/library`, `/app`, `/vocabulary?q=a` redirect guests to `/signin?next=...`; `//evil.com`, `https://evil.com`, `/\evil.com` are dropped; signed-in `/signin` goes to `/app` or `next`. |
| Backend `ruff check`, `ruff format --check`, `mypy` | Pass (`make` is not installed on this machine, so the commands were run through `uv`). |
| Backend `pytest` | Not fully run. Unit tests: 391 passed, 3 errors from a temp-directory permission error (`PermissionError` on `%TEMP%\pytest-of-Quoc Thai`). Integration tests need `TEST_DATABASE_URL` pointing at a dedicated `aprkb_test` database, which is not set here, so they were skipped. The branch does not change the backend. |

## Not done, on purpose or not possible

- **e2e (Playwright).** `apps/web/e2e/*.spec.ts` still targets the old UI (two failures were already known before the redesign). Owner decides: rewrite and switch back on, or delete.
- **Mobile and tablet.** Not built or tested (owner decision). Columns stack below 1024px only because the grid does.
- **Landing translated copy test.** The long pseudo-Vietnamese copy check from the plan was not run; the landing is English only for now, and is built so a `copy.vi.ts` can be added.
- **Admin key.** Gold, Extract, `/admin` and the create-key dialog were not exercised with an admin key. The demo session is a curator, so the admin APIs return 403 and those screens show only their empty or locked states. Needs a run with an admin key.
- **Reference library.** The phrasebank's Manchester collection is off in this environment (`REFERENCE_LIBRARY_ENABLED=false`), so only its disabled state was seen.
- **Screens that still use mock data** (`shared/api/mock-data.ts`, `mock-engine.ts`, `mock-integration.ts`, `mock-types.ts`): Library, Playground, Inbox, Journals and `/app` figures. Names and totals are plausible but invented.

## Pictures

Landing pictures and the clip are archival, openly licensed (public domain, CC0, one CC BY-SA 4.0 clip) and credited in the footer; see `261104-landing-report.md`. They are planned to be replaced by real app screenshots now that the app screens are final.

## Follow-ups worth a decision

1. Rewrite or delete the e2e specs.
2. Run Gold, Extract and Admin with an admin key and fix anything the empty states hid.
3. Split the 711 kB main chunk by route.
4. Replace the landing's archival pictures with app screenshots.
5. A polish pass (Phase 07) if the screens feel plain: summary figures on large screens, richer empty states, denser tables.
6. Commit the owner's own changes that were left out of the redesign commits: `CLAUDE.md`, `Makefile`, `README.md`, `SCAFFOLD_PRD.md`, `.codex/hooks.json`, `apps/web/src/features/slr-import/api/client.ts`.
