# ADR-0003: OpenAlex là adapter tùy chọn, bất đồng bộ

- Trạng thái: Superseded bởi [ADR-0005](0005-external-article-source.md)
- Ngày: 2026-10-29

## Bối cảnh
BR-05, BR-06, NFR-01, AT-04 và Gate D yêu cầu hệ thống core hoạt động khi OpenAlex lỗi hoặc bị tắt.

## Quyết định
- Module `openalex` chỉ được gọi từ worker (sync taxonomy, lookup DOI/ISSN, discovery).
- Kết quả lưu vào bảng local kèm `synced_at`, `classifier_version` và snapshot/diff.
- Module core (`recommendation`, `validation`, `patterns`...) không import `openalex`; chỉ đọc bảng local.
- Gọi HTTP bằng `httpx` + `tenacity` (backoff khi gặp 429), bật/tắt bằng `OPENALEX_ENABLED`.
- Không dùng OpenAlex ID làm khóa chính cho PhrasePattern.

## Hệ quả
- Dữ liệu phân loại có thể cũ; UI hiển thị cờ stale-sync.
- Gate D chạy test e2e với `OPENALEX_ENABLED=false`.
