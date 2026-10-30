# ADR-0004: Frontend React SPA + client sinh từ OpenAPI

- Trạng thái: Accepted
- Ngày: 2026-10-29

## Quyết định
- React + TypeScript + Vite, dạng SPA (không có nhu cầu SEO nên không cần SSR/Next.js).
- TanStack Query/Router/Table; UI dùng shadcn/ui trên Radix để đáp ứng accessibility (NFR-08).
- Type sinh từ `packages/contracts/openapi/openapi.json` bằng `openapi-typescript`, gọi API qua `openapi-fetch`.
- Mỗi màn hình WB-01 … WB-09 là một feature folder.

## Hệ quả
- Contract backend thay đổi thì frontend lỗi lúc build thay vì lúc chạy.
