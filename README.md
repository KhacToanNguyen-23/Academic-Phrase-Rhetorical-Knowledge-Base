# AP-RKB — Academic Phrase & Rhetorical Knowledge Base

Academic Wordbank: gợi ý và kiểm định câu học thuật theo rhetorical intent, discipline,
journal/genre và evidence. Tài liệu yêu cầu: [doc/](doc/).

## Kiến trúc

```
                ┌────────────────────────── apps/web (React SPA) ──────────────────────────┐
                │ WB-01 … WB-09                                                            │
                └───────────────────────────────┬──────────────────────────────────────────┘
                                                │ REST /v1 (OpenAPI)
 Writing Engine ───── scoped token ─────────────┤
                                                ▼
        ┌──────────────────── apps/backend (modular monolith, package aprkb) ─────────────┐
        │  api (FastAPI)                               worker (Celery)                     │
        │  taxonomy · patterns · journals              corpus ingest · mining · fingerprint│
        │  recommendation · validation · review        openalex sync (optional adapter)    │
        │  identity · audit · analytics                                                    │
        └───────────────┬──────────────────────────────────────┬───────────────────────────┘
                        ▼                                      ▼
            PostgreSQL 16 (+pgvector, pg_trgm, ltree)        Redis
                                                  (M2) GROBID · LanguageTool · OpenAlex API
```

Nguyên tắc chốt (xem [doc/adr/](doc/adr/)):
- Modular monolith; tách module theo domain trong PRD.
- OpenAlex là adapter tùy chọn, chỉ chạy trong worker và ghi vào DB local; core không gọi trực tiếp.
- Hard gates chạy trước ranking; version đã approved là bất biến; mọi quyết định đều được audit.

## Cấu trúc repo

```
apps/backend/        FastAPI + Celery (Python 3.12, uv)
apps/web/            React + TypeScript + Vite (pnpm)
packages/contracts/  OpenAPI + JSON Schema (import/export, Writing API)
data/seed/           Taxonomy, pattern tự biên soạn, journal profile khởi tạo
infra/               Cấu hình hạ tầng (Postgres init...)
doc/                 PRD, System Design, ADR
```

## Bắt đầu

```bash
cp .env.example .env
docker compose up -d postgres redis      # hạ tầng
docker compose up api worker             # backend
cd apps/web && pnpm install && pnpm dev  # frontend
docker compose --profile nlp up -d       # (M2) GROBID + LanguageTool
```

## Roadmap

| Release | Phạm vi |
|---|---|
| M0 Data foundation | taxonomy, canonical schema, rights policy, editor workflow |
| M1 Core MVP | patterns, search/recommendation, composer, validation, journal profile |
| M2 Corpus Intelligence | corpus, mining & review, fingerprint theo genre |
| M3 Discipline Intelligence | OpenAlex sync/affinity, ablation evaluation |
