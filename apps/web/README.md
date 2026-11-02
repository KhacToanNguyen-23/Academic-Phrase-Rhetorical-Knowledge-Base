# AP-RKB Web

`/writer` is the live Online demo backed by API + PostgreSQL. Library, Playground, Inbox, Journals and Admin remain prototype screens using mock data. Staff screens require a curator/admin API key; this is role-gated development access, not a full username/password account system or production admin console.

React + TypeScript + Vite (SPA). Gọi backend qua client sinh từ OpenAPI.

```
src/
  app/        App root, router, providers
  features/   mỗi màn hình PRD-10 một thư mục (components/ + api/)
  shared/     api (client sinh tự động), ui (shadcn/Radix), lib
e2e/          Playwright — Gate D: WB-01 → WB-08 với OpenAlex tắt
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

Quy tắc: feature không import lẫn nhau; dùng chung qua `shared/`.
UI luôn phân biệt nhãn **Required by journal / Observed in corpus / Model suggestion** (BR-04, BR-09, Gate C).

```bash
pnpm install
pnpm gen:api   # sau khi backend xuất openapi.json
pnpm dev
```

Open `http://localhost:5173/writer` after starting the backend and PostgreSQL.
Enter a client API key; the Writer page keeps it only in memory. `src/features/playground/live/api.ts`
uses OpenAPI types and the real `/v1` endpoints, with no mock fallback. The form
loads taxonomy and reference options from the DB. Journal-specific ranking and
full V01–V08 validation are shown as unavailable until reviewed data/rules exist.

The staff shell accepts curator/admin API keys and keeps the key in the current
tab's session storage. The local-only Quick demo button seeds self-authored sample
data and issues a curator key; it requires the Vite development server and a
loopback backend with `APP_ENV=local`.
The existing `npm run lint` script needs an ESLint 9 flat config before it can run.

The browser check is `npx playwright test e2e/writer.spec.ts`. Run it with
API/Vite against a seeded disposable `aprkb_test` database and set
`WRITER_E2E_API_KEY` to a client key for that database. On Windows,
`WRITER_E2E_BROWSER=msedge` uses the installed Edge browser.
