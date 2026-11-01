# Phase 02 — Bảng gold, nhãn, hướng dẫn, lấy mẫu

Trạng thái: chờ duyệt.

## Tài liệu

- Cập nhật `SCAFFOLD_PRD.md`: thêm gold dev (LLM gán nhãn, một người duyệt), API `/v1/admin/gold/*`, màn hình duyệt gold vào D11; bỏ dòng "gold chờ API bài báo" ở mục 14.
- ADR-0008 "Gold dev: LLM gán nhãn, một người duyệt": lý do, lệch FR-06.6, giới hạn `APP_ENV`, rủi ro anchoring.
- `eval/mining/gold/GUIDELINE.md`: định nghĩa từng nhãn kèm ví dụ **tự viết**. Đây cũng là system prompt của LLM (phiên bản `guideline_version`).
- `eval/mining/README.md`, `FORMAT.md`: mô tả gold mới; xóa template hai editor và `DEV_PROTOCOL.md`/`ANNOTATION_STATUS.md` cũ.

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

`id`, `article_id` (FK), `sentence_id` (FK, nullable khi ingest lại), `char_start`, `char_end`, `text_sha256`, `section_at_sampling`, `split` (`dev`/`test`), `sample_batch`, `guideline_version`,
`ai_labels` JSONB, `ai_model`, `ai_prompt_version`, `ai_labeled_at`,
`final_labels` JSONB, `status` (`pending_ai` → `draft` → `approved` / `rejected`; `label_failed`), `reviewed_by` (FK `api_clients`), `reviewed_at`, timestamps.

Không lưu text câu trong bảng này; text đọc từ `sentences` khi cần và kiểm tra `text_sha256` (lệch thì đánh dấu `stale`).

## Lấy mẫu

`POST /v1/admin/gold/samples` `{size: 300, seed, stratify: "section"}` (role curator): chọn câu đã qua `sentence_filter` **và** một phần câu bị lọc (để đo lọc nhiễu), phân tầng theo section, tối đa N câu mỗi bài, gán `split` theo seed, tạo `gold_items` trạng thái `pending_ai`, tạo job `label_gold`. Chỉ lấy bài có `allows_mining=true`.

## Kiểm tra

Unit: schema nhãn (giá trị lạ, slot ngoài câu), lấy mẫu tất định theo seed. Integration: tạo mẫu, không chọn câu của bài không có quyền mining, audit không chứa câu.
