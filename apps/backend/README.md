# AP-RKB Backend

Modular monolith (FastAPI + Celery) dùng chung package `aprkb`.

```
src/aprkb/
  core/       config, db, security, logging
  shared/     enum, versioning dùng chung
  api/        FastAPI app + gom router /v1
  worker/     Celery app + tasks nền (ingest, OpenAlex sync, mining, fingerprint)
  modules/    mỗi domain: models · schemas · repository · service · router
migrations/   Alembic
tests/        unit · integration · acceptance (AT-01…AT-12)
```

## Module ↔ PRD

| Module | PRD | Ưu tiên |
|---|---|---|
| taxonomy | PRD-01 | P0 |
| patterns | PRD-02 | P0 |
| journals | PRD-05 | P0 profile / P1 fingerprint |
| recommendation | PRD-07 | P0 |
| validation | PRD-08 | P0 |
| identity, audit | PRD-00.2, NFR-03/04 | P0 |
| corpus | PRD-04 | P1 |
| mining, review | PRD-06 | P1 |
| analytics | PRD-09 | P1 |
| openalex | PRD-03 | P2 (metadata P1) |

## Quy tắc phụ thuộc giữa module

- Module chỉ gọi module khác qua `service.py`, không import `models`/`repository` của nhau.
- `taxonomy` không phụ thuộc module nào; `patterns` → `taxonomy`;
  `recommendation` → `patterns`, `taxonomy`, `journals`, `validation`.
- **Không module core nào import `openalex`.** Dữ liệu OpenAlex đi vào DB local qua worker;
  core chỉ đọc bảng local (BR-06, NFR-01).
- Mọi thay đổi trạng thái quan trọng ghi `audit` trong cùng transaction (NFR-03).

## Chạy local

```bash
uv sync
uv run alembic init migrations   # lần đầu, khi bắt đầu M0
uv run uvicorn aprkb.api.main:app --reload
uv run pytest
```
