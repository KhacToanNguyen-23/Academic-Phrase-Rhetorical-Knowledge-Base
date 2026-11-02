# Phase 08 — Đánh giá trên gold đã duyệt

Trạng thái: evaluator và CLI đã triển khai. Chưa chạy vì chưa có nhãn `approved`; không tạo score/quality claim thay người duyệt.

## Việc

Lệnh `uv run --directory apps/backend python -m aprkb.cli eval-mining [--split dev|test]`:

- Chỉ đọc item `approved` và không `stale`.
- Chạy các stage hiện có trên đúng câu đó, so với `final_labels`.
- Báo cáo tách hai thuật toán (2026-11-02):
  - `sentence_filter`: precision/recall của `keep`; `noise_reason_confusion` là bảng đếm thô giữa lý do nhiễu của gold và lý do loại của bộ lọc (không giả định ánh xạ giữa hai danh sách).
  - `extraction`: chạy các stage sau bộ lọc trên mọi câu gold `keep=true` (bất kể bộ lọc có cho qua không). Gồm `gold_keep_count`, `extracted_count`, `coverage` và `reasons` (số câu theo `extractability_reason`).
  - `accuracy`, `confusions`, `slot_f1` chỉ tính trên câu đã trích, đọc cùng `coverage`: section, `epistemic_strength`, `tense`, `ownership`, frame (khớp chính xác sau chuẩn hóa khoảng trắng), slot (F1 theo vị trí ký tự).
- Báo cáo riêng `dev` và `test`, kèm phiên bản policy/stage, `guideline_version` và số item. Ghi ra stdout và `data/eval/` (gitignored). Không in câu.
- Thêm vào báo cáo tỉ lệ người duyệt sửa nhãn AI theo từng trường (độ tin cậy của nhãn nháp).

## Kiểm tra

Unit: tính số liệu trên dữ liệu tự viết với kết quả biết trước. Integration: bỏ qua item `draft`/`rejected`/`stale`.

Chạy sau khi có nhãn người duyệt: `uv run --directory apps/backend python -m aprkb.cli eval-mining --split dev` hoặc `--split test`. Report chỉ có metric tổng hợp, policy version, item count và số item stale; file nằm trong `apps/backend/data/eval/` (ignored).
