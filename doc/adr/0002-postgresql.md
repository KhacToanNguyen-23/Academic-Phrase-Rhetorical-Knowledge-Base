# ADR-0002: PostgreSQL là kho dữ liệu duy nhất ở MVP

- Trạng thái: Accepted
- Ngày: 2026-10-29

## Quyết định
PostgreSQL 16 với các extension:
- `ltree` / recursive CTE: cây taxonomy Section → Move → Step → Intent.
- `JSONB`: `slots_schema`, `constraints`, `features` của fingerprint.
- `pg_trgm` + full-text search: tìm kiếm (FR-07.1, p95 < 1,5s ở quy mô MVP).
- `pgvector`: near-duplicate, clustering, diversification (FR-02.5, FR-06.3, FR-07.6).

Version bất biến: bảng `*_version` chỉ append; trigger chặn UPDATE/DELETE trên bản ghi `approved`.
Audit: bảng `audit_event` append-only, ghi trong cùng transaction với thay đổi.

## Hệ quả
- Không cần Elasticsearch hay vector DB riêng ở M0–M2. Xem xét lại khi corpus vượt ngưỡng hiệu năng.
- Không dùng Neo4j vì taxonomy nông và quan hệ đã đủ biểu diễn bằng SQL.
