# ADR-0005: Nhập bài báo từ API nguồn ngoài, bỏ OpenAlex

- Trạng thái: Accepted
- Ngày: 2026-10-30
- Thay thế: [ADR-0003](0003-openalex-optional-adapter.md)
- Bổ sung bởi: [ADR-0006](0006-slr-repository-import.md) (nguồn SLR, bộ lọc `ImportProfile`)

## Bối cảnh
Hệ thống không dùng OpenAlex. Bài báo để mining được lấy từ một API nguồn ngoài, trả nội dung dạng PDF hoặc Markdown kèm license của từng bài. Module `openalex` chỉ là khung rỗng, không có module nào phụ thuộc.

## Quyết định
- Xóa module `openalex` và config `OPENALEX_*`. Giữ `DisciplineSource` + `NullDisciplineSource` để sau này nối nguồn phân loại ngành nếu cần.
- Nguồn bài báo là một `ArticleSource` (`modules/corpus/sources/`) với hai bước: `list_articles(cursor, limit)` chỉ trả metadata, `fetch_content(ref)` tải nội dung.
- Chỉ worker gọi nguồn, qua job `import_articles`. Curator tạo job bằng `POST /v1/admin/corpus/imports`; trang tiếp theo được xếp hàng thành job mới theo `next_cursor`.
- **License được kiểm tra trên metadata trước khi tải nội dung** (fail closed): license thiếu, không có trong bảng `licenses`, hoặc `allows_mining = false` thì bỏ qua, không tải, không lưu blob.
- Bài được nhập đi tiếp qua luồng ingest hiện có (blob → `Article` → job `ingest_article`). Cặp `(source, external_id)` là unique; DOI trùng cũng bị bỏ qua.
- Audit `corpus.import.page` chỉ ghi số lượng và cursor, không ghi nội dung bài.
- Chọn adapter bằng `ARTICLE_SOURCE`; mặc định `null`, khi đó endpoint import trả `409`.
- Markdown được parse thật (heading ATX → section). PDF vẫn là stub, nên bài PDF sẽ được lưu nhưng ingest báo lỗi cho đến khi có parser.

## Hệ quả
- Adapter HTTP thật cho API đã chọn còn là `TODO(owner, PRD-04)`, gồm cả việc map license của nguồn sang mã trong bảng `licenses`.
- Nguồn lỗi hoặc bị tắt chỉ làm job import thất bại; recommendation và validation chỉ đọc dữ liệu local nên vẫn chạy (AT-04).
- Cần xác nhận điều khoản sử dụng (ToS) của API cho phép text mining và lưu trữ nội dung.
