# Phase 03 — Gán nhãn bằng LLM

Trạng thái: đã triển khai adapter, worker job và mocked tests. Owner đã cấu hình Groq key trong `.env` local và chọn model `openai/gpt-oss-120b`; chưa gọi Groq thật khi chưa xác nhận quyền xử lý bài báo từ bên thứ ba.

## Thiết kế

- Interface `GoldLabeler` (`modules/gold/labelers/`), không phụ thuộc nhà cung cấp:
  - `NullGoldLabeler` (mặc định): báo lỗi rõ khi chưa cấu hình.
  - `GroqGoldLabeler`: dùng `httpx` đã có sẵn để gọi Chat Completions endpoint chính thức của Groq; test dùng `httpx.MockTransport`, không gọi mạng. [Groq API reference](https://console.groq.com/docs/api-reference).
  - Nhà cung cấp khác (ví dụ Anthropic) thêm sau bằng một class mới, không đổi job hay API.
- Config: `GOLD_LABELER` (`null` | `groq`, mặc định `null`). Key đọc từ `GROQ_API_KEY` trong `.env` local khi owner chủ động chạy thật; không đưa key vào policy, code, repo, API, logs hay audit. Không làm UI nhập key, lưu DB, mã hóa server-side, master key, rotation hoặc revoke trong giai đoạn dev này. Giữ Groq tắt mặc định; chỉ bật cho lần chạy được owner chủ động yêu cầu. `allows_mining` không mặc nhiên cho phép gửi câu ra bên thứ ba; giữ `TODO(owner, BR-10)` trước khi xử lý dữ liệu không được xác nhận quyền.
- `policies/gold_labeling.yaml`: `provider`, `model`, `temperature`, `max_tokens`, `sentences_per_request`, `max_concurrency`, `requests_per_minute`, `prompt_version`, `guideline_version`; model do owner chọn, các giới hạn tạm có `TODO(owner, FR-06.3)`. Provider policy là Groq; runtime vẫn tắt nếu thiếu `GOLD_LABELER=groq`, key hoặc quyền xử lý bên ngoài.
- Prompt: system = `GUIDELINE.md` + mô tả JSON schema của nhãn; user = câu đích, câu trước/sau cùng section. Slot offsets luôn tính trên câu đích. Không log prompt/request/response.
- Output: yêu cầu JSON (JSON mode / json_schema nếu model hỗ trợ), **luôn validate lại bằng Pydantic** phía mình. Sai schema, slot ngoài câu, thiếu câu → item `label_failed`, không đoán hay tự sửa.
- Giới hạn tốc độ: tuần tự theo `requests_per_minute`, tôn trọng `retry-after` tối đa ba lần khi gặp 429. Lỗi HTTP/provider làm job thất bại với thông báo đã làm sạch; JSON/schema/offset lỗi đánh dấu item `label_failed`.
- Job worker `label_gold`: lấy item `pending_ai` của một `sample_batch`, kiểm tra lại `allows_mining` và `APP_ENV`, gọi labeler, ghi `ai_labels`, `ai_model`, `ai_prompt_version`, đặt `status=draft` (chưa phải gold). `jobs.result`: số item gán được, thất bại, token.
- Log/audit/job result: chỉ id và số lượng. Không log câu, prompt, response, API key hay token usage từ provider.

## Kiểm tra

- Unit: labeler với HTTP giả lập (không gọi API thật): JSON hợp lệ, JSON hỏng, sai schema, slot ngoài câu, thiếu câu trong batch, 429 có `retry-after`, 401.
- Integration: job `label_gold` với labeler giả → item chuyển `draft`; bài mất quyền mining → không gửi.
- Chạy thật bằng tay với khoảng 10 câu, xem tỉ lệ `label_failed`, rồi mới chạy cả 300. Owner đã chọn model `openai/gpt-oss-120b` và báo đã cấu hình key local; chỉ chạy sau khi xác nhận quyền gửi dữ liệu cho dịch vụ bên thứ ba.

Trước khi queue job, cần `GOLD_LABELER=groq`, `GROQ_API_KEY` trong `.env` và `GROQ_ALLOW_EXTERNAL_PROCESSING=true` **chỉ sau khi owner xác nhận quyền gửi dữ liệu**. Key/model đã được owner cấu hình; không gọi Groq trong test hoặc lần triển khai này khi quyền gửi dữ liệu chưa được xác nhận.
