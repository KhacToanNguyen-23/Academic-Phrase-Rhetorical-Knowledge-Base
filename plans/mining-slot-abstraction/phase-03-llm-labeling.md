# Phase 03 — Gán nhãn bằng LLM

Trạng thái: chờ duyệt. Owner quyết định ngày 2026-11-01: **tạm test bằng model của Groq**; key do owner cấp khi cần chạy thật.

## Thiết kế

- Interface `GoldLabeler` (`modules/gold/labelers/`), không phụ thuộc nhà cung cấp:
  - `NullGoldLabeler` (mặc định): báo lỗi rõ khi chưa cấu hình.
  - `GroqGoldLabeler`: dùng SDK `groq` chính thức (kiểm tra tài liệu Groq khi cài đặt, không đoán API).
  - Nhà cung cấp khác (ví dụ Anthropic) thêm sau bằng một class mới, không đổi job hay API.
- Config: `GOLD_LABELER` (`null` | `groq`, mặc định `null`), `GROQ_API_KEY` (`SecretStr`, rỗng = tắt). Bật labeler thật ngoài `APP_ENV` local/test thì app không khởi động. `TODO(owner, BR-10)`: quyền gửi câu bài báo cho bên thứ ba.
- `policies/gold_labeling.yaml`: `provider`, `model` (owner chọn model Groq khi cấp key, `TODO(owner)`), `temperature`, `max_tokens`, `sentences_per_request`, `max_concurrency`, `requests_per_minute`, `prompt_version`, `guideline_version`.
- Prompt: system = `GUIDELINE.md` + mô tả JSON schema của nhãn; user = các câu cần gán kèm câu trước/sau và tiêu đề section.
- Output: yêu cầu JSON (JSON mode / json_schema nếu model hỗ trợ), **luôn validate lại bằng Pydantic** phía mình. Sai schema, slot ngoài câu, thiếu câu → item `label_failed`, không đoán hay tự sửa.
- Giới hạn tốc độ: Groq có rate limit theo model; tôn trọng `retry-after` khi gặp 429, giới hạn song song theo policy. Lỗi 4xx khác → fail job với mã lỗi, không kèm nội dung.
- Job worker `label_gold`: lấy item `pending_ai` của một `sample_batch`, kiểm tra lại `allows_mining` và `APP_ENV`, gọi labeler, ghi `ai_labels`, `ai_model`, `ai_prompt_version`, đặt `status=draft` (chưa phải gold). `jobs.result`: số item gán được, thất bại, token.
- Log: chỉ id, số lượng, token, thời gian. Không log câu, prompt hay response.

## Kiểm tra

- Unit: labeler với HTTP giả lập (không gọi API thật): JSON hợp lệ, JSON hỏng, sai schema, slot ngoài câu, thiếu câu trong batch, 429 có `retry-after`, 401.
- Integration: job `label_gold` với labeler giả → item chuyển `draft`; bài mất quyền mining → không gửi.
- Chạy thật bằng tay (cần `GROQ_API_KEY` và tên model từ owner) với ~10 câu, xem tỉ lệ `label_failed`, rồi mới chạy cả 300.
