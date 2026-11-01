# Phase 02 — Bảng gold, nhãn, hướng dẫn, lấy mẫu

Trạng thái: hoàn thành — schema, API lấy mẫu deterministic, guideline, PRD/ADR và mẫu dev đã cập nhật.

## Tài liệu

- Cập nhật `SCAFFOLD_PRD.md`: thêm gold dev (LLM gán nhãn, một người duyệt), API `/v1/admin/gold/*`, màn hình duyệt gold vào D11; bỏ dòng "gold chờ API bài báo" ở mục 14.
- ADR-0008 "Gold dev: AI gán nhãn nháp, một người duyệt cuối mọi nhãn": giới hạn khác biệt với FR-06.6 validation hai editor, quyền xử lý AI.
- `eval/mining/gold/GUIDELINE.md`: định nghĩa từng nhãn kèm ví dụ **tự viết**. Đây cũng là system prompt của LLM (phiên bản `guideline_version`).
- `eval/mining/README.md`, `FORMAT.md`, `DEV_PROTOCOL.md`, `ANNOTATION_STATUS.md`: mô tả gold dev một reviewer, ghi rõ khác với validation hai editor theo FR-06.6 và chưa có nhãn.

## Nhãn (Pydantic, dùng chung cho LLM, API và evaluator)

| Trường | Giá trị |
|---|---|
| `keep` | bool — câu có dùng để trích phrase được không |
| `noise_reason` | `caption` / `table` / `formula` / `reference` / `acknowledgement` / `fragment` / `metadata` / `other`, chỉ khi `keep=false` |
| `section` | mã section trong bảng `sections` hoặc `OTHER` |
| `epistemic_strength` | `low` / `moderate` / `high` / `absolute` / `none` (theo `epistemic_markers.yaml`) |
| `tense` | `past` / `present` / `present_perfect` / `none` (thì của động từ tường thuật chính) |
| `frame` | khung phrase, slot đặt tên theo vị trí `[X]`, `[Y]`, `[Z]` |
| `slots` | danh sách `{name, char_start, char_end}` trong câu |
| `ownership` | `own` / `prior` / `unclear` (DET_OWN/DET_PRIOR) |
| `notes` | ghi chú ngắn của người duyệt (tùy chọn) |

`intent` (move) chưa gán ở v0.

## Bảng `gold_items` (migration sau head hiện tại)

`id`, `article_id` (FK), `sentence_id` (FK, nullable khi ingest lại), `char_start`, `char_end`, `text_sha256`, `section_at_sampling`, `split` (`dev`/`test`), `sample_batch`, `guideline_version`, `ai_labels` JSONB, `ai_model`, `ai_prompt_version`, `ai_labeled_at`, `final_labels` JSONB, `reviewed_by`, `reviewed_at`, `status`, timestamps.

AI gán nhãn mọi item; một người reviewer duyệt tất cả nhãn, chấp nhận hoặc sửa để tạo `final_labels`. Không gộp nhãn AI thành nhãn người duyệt. Quy trình này không thay thế validation gold hai editor theo FR-06.6.

Không lưu text câu trong bảng này; text đọc từ `sentences` khi cần và kiểm tra `text_sha256` (lệch thì đánh dấu `stale`).

## Lấy mẫu

`POST /v1/admin/gold/samples` `{size: 300, seed, stratify: "section"}` (role curator): chọn câu đã qua `sentence_filter` **và** một phần câu bị lọc (để đo lọc nhiễu), phân tầng theo section, tối đa N câu mỗi bài, gán `split` theo seed, tạo `gold_items` trạng thái `pending_ai`. Chỉ lấy bài `source=slr` và `allows_mining=true`. Tỉ lệ nằm trong `policies/gold_sampling.yaml`: `filtered_fraction` (10%) lấy từ câu bị `sentence_filter` loại, chia đều theo lý do loại; phần còn lại chia đều theo section của câu được giữ; `test_fraction` (30%) chọn riêng trong từng tầng (từng section, và nhóm bị lọc), tổng đúng bằng round(size × 0,3). Nếu một pool thiếu quota thì pool còn lại bù. Job `label_gold` chỉ được tạo ở Phase 03 khi worker handler đã tồn tại.

Audit tạo mẫu ghi `filtered_count` và `sampling_policy_version`. Từ repo root, dọn batch bằng `uv run --directory apps/backend python -m aprkb.cli delete-gold-batch --sample-batch <id>`; chỉ xóa khi không item nào có `ai_labels` hoặc `final_labels`. Xóa và audit `gold.sample.delete` nằm trong cùng transaction.

## Kiểm tra

Unit: schema nhãn (giá trị lạ, slot ngoài câu), lấy mẫu tất định theo seed. Integration: tạo mẫu, không chọn câu của bài không có quyền mining, audit không chứa câu. Kiểm tra split test 30% theo seed.
