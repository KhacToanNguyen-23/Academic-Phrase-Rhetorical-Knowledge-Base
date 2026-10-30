# Contracts

Run `make contracts` from the repository root to export the backend OpenAPI document and regenerate the frontend TypeScript schema. CI checks that both generated artifacts are current. The frontend's mock data types remain separate while the UI is a prototype.

- `openapi/openapi.json`: xuất từ backend FastAPI. Là nguồn sự thật cho frontend và Writing Engine (FR-09.1).
- `json-schema/`: schema cho import/export taxonomy và pattern (FR-01.5, FR-09.5).

Thay đổi phá vỡ contract phải tăng version API (`/v2`) hoặc version schema.
