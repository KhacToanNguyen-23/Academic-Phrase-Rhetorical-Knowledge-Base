# Phase 07 — Duyệt gold trên web

Trạng thái: chờ duyệt.

## API (role reviewer trở lên)

- `GET /v1/admin/gold/items?status=&split=&section=&cursor=`: danh sách, không kèm text.
- `GET /v1/admin/gold/items/{id}`: nhãn AI, nhãn cuối, text câu + câu trước/sau + tiêu đề section. Trả text chỉ khi license `allows_display=true` và `text_sha256` còn khớp; nếu không thì `409` kèm lý do.
- `POST /v1/admin/gold/items/{id}/review` `{decision: approve | reject, final_labels?, notes?}`: approve không kèm `final_labels` = chấp nhận nhãn AI; có `final_labels` = duyệt kèm sửa. Ghi `reviewed_by`, `reviewed_at`, audit (trường nào đổi, không chứa câu).
- `GET /v1/admin/gold/stats`: số item theo trạng thái/split/section, tỉ lệ AI bị sửa theo từng trường.
- `POST /v1/admin/gold/samples` (phase 02) và nút gán nhãn lại cho item `label_failed`.

## Màn hình `/gold`

- Thanh tiến độ: đã duyệt / tổng, tỉ lệ sửa.
- Danh sách bên trái lọc theo trạng thái, split, section.
- Khung chính: câu (slot tô màu theo vị trí), ngữ cảnh mờ, form nhãn điền sẵn nhãn AI (dropdown cho các trường enum, ô frame, chọn slot bằng cách bôi đen trong câu).
- Nút **Duyệt** / **Duyệt kèm sửa** (tự nhận biết khi form khác nhãn AI) / **Loại**; phím tắt `A`, `R`, `J/K` chuyển câu; duyệt xong tự sang câu kế.
- Theo style CSS hiện có, gọi API qua client OpenAPI, kiểm tra lỗi theo HTTP status (`unwrap`).

## Kiểm tra

Integration: quyền (client bị 403), duyệt/sửa/loại, không trả text khi `allows_display=false` hoặc hash lệch, audit không chứa câu. Web: typecheck, lint; chạy thử bằng tay trên vài item.
