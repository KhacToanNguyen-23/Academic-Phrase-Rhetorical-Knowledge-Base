# AP-RKB Web

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
| search-explorer | WB-01 | Writer |
| pattern-detail | WB-02 | Writer, Editor |
| sentence-composer | WB-03 | Writer |
| journal-profile | WB-04 | Journal Analyst |
| taxonomy-manager | WB-05 | Editor |
| corpus-workbench | WB-06 | Corpus Curator |
| pattern-review | WB-07 | Editor |
| validation-console | WB-08 | Writer |
| admin | WB-09 | Administrator |

Quy tắc: feature không import lẫn nhau; dùng chung qua `shared/`.
UI luôn phân biệt nhãn **Required by journal / Observed in corpus / Model suggestion** (BR-04, BR-09, Gate C).

```bash
pnpm install
pnpm gen:api   # sau khi backend xuất openapi.json
pnpm dev
```
