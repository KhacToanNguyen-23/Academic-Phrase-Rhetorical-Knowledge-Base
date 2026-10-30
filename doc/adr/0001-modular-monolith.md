# ADR-0001: Modular monolith Python (FastAPI + Celery)

- Trạng thái: Accepted
- Ngày: 2026-10-29

## Bối cảnh
- Phase P1 cần pipeline NLP (GROBID/TEI, n-gram mining, clustering, spaCy, embeddings), hệ sinh thái mạnh nhất là Python.
- Version, audit và workflow duyệt cần transaction xuyên module (NFR-03, NFR-07).
- Team nhỏ, MVP mang tính nghiên cứu.

## Quyết định
- Một package Python `aprkb` với hai entrypoint: `api` (FastAPI) và `worker` (Celery + Redis).
- Mỗi domain trong PRD là một module `modules/<name>`, giao tiếp với module khác qua `service.py`.
- Contract API định nghĩa bằng Pydantic và xuất OpenAPI vào `packages/contracts`.

## Hệ quả
- Một ngôn ngữ backend, triển khai đơn giản.
- Khi cần scale thì tách worker NLP thành service riêng trước.
- Cần kỷ luật import giữa các module (có thể kiểm bằng import-linter).

## Phương án bị loại
- Microservices: chi phí vận hành cao, transaction phân tán.
- NestJS/Spring: vẫn phải có Python cho NLP, thành hai backend.
