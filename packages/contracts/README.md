# Contracts

- `openapi/openapi.json`: xuất từ backend FastAPI. Là nguồn sự thật cho frontend và Writing Engine (FR-09.1).
- `json-schema/`: schema cho import/export taxonomy và pattern (FR-01.5, FR-09.5).

Thay đổi phá vỡ contract phải tăng version API (`/v2`) hoặc version schema.
