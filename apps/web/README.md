# AP-RKB Web

This frontend is a prototype UI and remains outside the scaffold's backend runtime scope. Its current screens use local mock data and mock API behavior. The admin screen is not a completed or in-scope production admin console.

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
| playground | WB-03 + WB-08 | Editor, Writing team |
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
