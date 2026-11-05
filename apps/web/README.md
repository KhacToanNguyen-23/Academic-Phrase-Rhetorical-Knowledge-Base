# AP-RKB Web

`/writer` is the live Online demo backed by API + PostgreSQL. Library, Playground, Inbox, Journals and Admin remain prototype screens using mock data. Staff screens require a curator/admin API key; this is role-gated development access, not a full username/password account system or production admin console.

React + TypeScript + Vite (SPA). Gọi backend qua client sinh từ OpenAPI.

```
src/
  app/          App root, router, providers, app shell (sidebar, command menu), globals.css (tokens)
  components/
    ui/         shadcn components (Radix), adjusted once to the design tokens
    domain/     PhraseFrame, DataState, PageHeader, StatusBadge, SelectField...
  features/     mỗi màn hình một thư mục (components/ + api/); landing/ is the public page
  shared/       api (client sinh tự động), lib
e2e/            Playwright — lab Phrasebank and PostgreSQL-backed Writer smoke tests
```

Routes: `/` public landing, `/signin`, `/app` staff workspace; every other screen keeps its path and is
guarded. Design decisions: [ADR-0011](../../doc/adr/0011-frontend-design-system.md).

### Design system

- Add a component: `pnpm dlx shadcn@latest add <name>` (Radix style, see `components.json`), then keep it to the
  tokens in `src/app/globals.css`. Use pnpm only; commit `pnpm-lock.yaml`.
- Tokens live in `globals.css`: `--brand` teal for the one primary action, the active nav item and slots; neutral
  everything else. Fonts: Be Vietnam Pro (sans) and Newsreader (phrases).
- Landing copy is in `src/features/landing/copy.en.ts`; add a locale by adding `copy.<lang>.ts` with the same type.
- `/dev/ui` shows every component in every state. It exists in development and in the inspect build only.
- Desktop only (1440px, minimum 1024px). One primary (teal) button per screen at most.

### Checks

```bash
pnpm typecheck && pnpm lint && pnpm build
pnpm build:inspect && pnpm preview:inspect       # port 4174, signs in with the local demo session
node ../../.agents/skills/design-taste-frontend/scripts/lint.mjs --app src
node ../../.agents/skills/design-taste-frontend/scripts/inspect.mjs --app http://127.0.0.1:4174/library --widths 1440
```

| Feature | Màn hình | Role chính |
|---|---|---|
| library | WB-01 + WB-02 | Editor |
| playground | WB-03 + WB-08 mock simulation | Editor, Writing team |
| writer | Online field → search → compose → validate → feedback | Writer |
| journal-profile | WB-04 | Journal Analyst |
| taxonomy-manager | WB-05 | Editor |
| corpus-workbench | WB-06 | Corpus Curator |
| inbox | WB-07 | Editor |
| admin | WB-09 | Administrator |
| slr-import | Import from SLR | Curator |

Quy tắc: feature không import lẫn nhau; dùng chung qua `shared/`.
UI luôn phân biệt nhãn **Required by journal / Observed in corpus / Model suggestion** (BR-04, BR-09, Gate C).

The `/import` screen calls the live backend API using the generated OpenAPI client. Configure `VITE_API_BASE_URL` for the API origin and enter an AP-RKB API key in the screen; it is held in `sessionStorage` for that browser session. It does not use the app mock engine. ESLint 9 uses the flat config in `eslint.config.js`.

```bash
pnpm install
pnpm gen:api   # sau khi backend xuất openapi.json
pnpm dev
```

Open `http://localhost:5173/writer` after starting the backend and PostgreSQL.
`src/features/playground/live/api.ts` uses OpenAPI types and the real `/v1`
endpoints, with no mock fallback. The form
loads taxonomy and reference options from the DB. Journal-specific ranking and
full V01–V08 validation are shown as unavailable until reviewed data/rules exist.

The staff shell accepts curator/admin API keys and keeps the key in the current
tab's session storage. The local-only Quick demo button seeds self-authored sample
data and issues a curator key; it requires the Vite development server and a
loopback backend with `APP_ENV=local`.
Run `pnpm test:e2e` with API/Vite against a seeded disposable `aprkb_test`
database. Phrasebank tests mock their API responses and cover the lab-only
collection. The Writer test uses the real API and the current Phrasebank Basic
seed data. CI runs this suite in `frontend-e2e-smoke` for push and pull request
events. On Windows, `WRITER_E2E_BROWSER=msedge` uses the installed Edge browser.
Failure traces and screenshots go to `test-results`; CI's HTML report goes to
the separate `playwright-report` directory.
