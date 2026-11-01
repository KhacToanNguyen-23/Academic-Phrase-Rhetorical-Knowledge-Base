# Phase 08 — Đánh giá trên gold đã duyệt

Trạng thái: evaluator và CLI đã triển khai. Chưa chạy vì chưa có nhãn `approved`; không tạo score/quality claim thay người duyệt.

## Việc

Lệnh `uv run --directory apps/backend python -m aprkb.cli eval-mining [--split dev|test]`:

- Chỉ đọc item `approved` và không `stale`.
- Chạy các stage hiện có trên đúng câu đó, so với `final_labels`.
- Số liệu: lọc nhiễu (precision/recall của `keep`), section (accuracy, confusion), `epistemic_strength` và `tense` (accuracy, confusion), `ownership`, frame (khớp chính xác sau chuẩn hóa khoảng trắng), slot (F1 theo vị trí ký tự).
- Báo cáo riêng `dev` và `test`, kèm phiên bản policy/stage, `guideline_version` và số item. Ghi ra stdout và `data/eval/` (gitignored). Không in câu.
- Thêm vào báo cáo tỉ lệ người duyệt sửa nhãn AI theo từng trường (độ tin cậy của nhãn nháp).

## Kiểm tra

Unit: tính số liệu trên dữ liệu tự viết với kết quả biết trước. Integration: bỏ qua item `draft`/`rejected`/`stale`.

Chạy sau khi có nhãn người duyệt: `uv run --directory apps/backend python -m aprkb.cli eval-mining --split dev` hoặc `--split test`. Report chỉ có metric tổng hợp, policy version, item count và số item stale; file nằm trong `apps/backend/data/eval/` (ignored).
