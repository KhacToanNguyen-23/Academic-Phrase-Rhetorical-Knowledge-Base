# Plan: Mining slot abstraction + gold dev từ bài SLR thật

Ngày: 2026-11-01 (thay bản 2026-10-31)
Rủi ro: cao — gửi câu bài báo cho LLM bên ngoài (Groq), thêm bảng và migration, thêm màn hình web.
Trạng thái: owner đã chốt phạm vi triển khai ngày 2026-11-01; đang triển khai.

## Thay đổi so với bản 2026-10-31

SLR import đã chạy được (4 bài thật, license `DEV-UNVERIFIED`), nên điều kiện "chờ API bài báo" đã đạt. Owner quyết định ngày 2026-11-01:

| Trước | Nay |
|---|---|
| Gold hoãn tới khi có API bài báo | Làm gold dev ngay, lấy mẫu khoảng 300 câu từ bài SLR thật |
| Hai editor gán nhãn độc lập, κ, phân xử (FR-06.6) | **AI gán nhãn mọi phrase; một người duyệt cuối tất cả nhãn AI.** Đây là quy trình gold dev theo quyết định owner, không đáp ứng yêu cầu validation hai editor của FR-06.6; không báo cáo inter-editor κ |
| AI hỗ trợ là đề xuất, chưa có code | Tích hợp LLM vào hệ thống qua interface `GoldLabeler`; tạm dùng **Groq**, cấu hình trong policy YAML |
| Không thêm endpoint, không thêm màn hình | Thêm API `/v1/admin/gold/*` và màn hình duyệt gold trên web |

Không đổi: luồng runtime upload/import → ingest → `mine_article` → candidate `pending` → hai vòng review. Mining không ghi pattern/version. Gold **không** đi vào review queue và không tạo pattern.

## Flow đã làm (cập nhật 2026-11-02)

```
SLR import → ingest (tách câu, section, lọc nhiễu) → lấy mẫu 300 câu (phân tầng)
  → Groq gán nhãn nháp → kiểm tra frame tự động → [người duyệt trên /gold] → gold approved
  → eval-mining: sentence_filter  |  extraction (slot_abstractor)
```

1. **Ingest (01):** tách câu biết chữ viết tắt, nhận diện section, lọc câu nhiễu; đã `reingest` 4 bài SLR (ví dụ 771→730, 705→647, 96→85, 1288→1276 câu).
2. **Lấy mẫu (02):** 300 câu, phân tầng theo section, 10% từ câu bị bộ lọc loại, 30% (90 câu) vào `test` và chọn riêng trong từng tầng. Chỉ lấy bài `source=slr`.
3. **Gán nhãn (03):** `GroqGoldLabeler` dùng `openai/gpt-oss-120b`, `json_schema` strict, `reasoning_effort: medium`, `include_reasoning: false`. Hết quota (429 đòi chờ lâu hơn `max_rate_limit_wait_seconds`) thì job dừng, giữ nhãn đã gán và báo `stopped: quota`. Tham số `limit` cho phép gán thử một phần batch.
4. **Chạy thử 10 câu:** 10/10 gán được, 0 `label_failed`, khoảng 124 giây và 21,8 nghìn token (~2,2 nghìn/câu). Ước tính 300 câu ≈ 654 nghìn token, vượt hạn mức ngày của gói miễn phí, nên cần chia nhiều ngày hoặc giảm effort. Hạn mức thật xem ở console.groq.com.
5. **Rà nhãn nháp:** 3/7 câu `keep=true` có frame không khớp câu gốc (mất phần đầu, phần cuối hoặc chữ bị sửa); một số frame còn nguyên từ chuyên ngành. Từ đó:
   - Thêm `GoldLabels.validate_frame_matches_source`: frame phải bằng câu với mỗi slot thay bằng `[tên]`. Chỉ áp dụng cho nhãn AI; lệch thì item thành `label_failed`.
   - Viết lại hướng dẫn thành **guideline v1** và prompt v1 (`prompt_version`, `guideline_version`).
6. **Chốt định nghĩa `keep` (v1):** `keep` = câu là văn xuôi sạch, không phải nhiễu. Nó **không** nghĩa là trích được slot. Bộ trích (`slot_abstractor`) chỉ chạy trên câu sạch và được đo riêng.
7. **Runtime (05):** `SlotAbstractor.extractability_reason(text)` trả `None` hoặc `no_reporting_verb` / `no_that` / `no_subject` / `subject_too_long` / `clause_too_short`.
8. **Evaluator (08):** tách thành `sentence_filter` (keep, noise_reason) và `extraction` (coverage, lý do, accuracy, slot F1 trên câu đã trích).

**Chưa có gold được duyệt, chưa có kết luận chất lượng.** 10 nhãn nháp hiện có là v0 (định nghĩa `keep` cũ), không nên duyệt làm gold; 290 câu còn `pending_ai`. Số đếm thử trên 10 nhãn nháp (độ phủ bộ trích 1/7, phần lớn `no_reporting_verb`) chỉ để minh họa, không phải kết quả đánh giá.

## Phase

| Phase | Nội dung | Trạng thái |
|---|---|---|
| [01](phase-01-ingest-quality.md) | Chất lượng ingest: tách câu với chữ viết tắt, nhận diện section, lọc câu nhiễu | Hoàn thành; đã `reingest` 4 bài SLR |
| [02](phase-02-gold-schema-and-guideline.md) | Bảng gold, nhãn (Pydantic), hướng dẫn gán nhãn, lấy mẫu, cập nhật PRD/ADR | Hoàn thành: schema/API, mẫu 300 item phân tầng (90 test), guideline v1; chưa có nhãn được duyệt |
| [03](phase-03-llm-labeling.md) | Gán nhãn bằng LLM (tạm dùng Groq) qua job worker, validate bằng Pydantic | Đã triển khai; đã chạy thật 10 câu bằng `openai/gpt-oss-120b` (10/10, nhãn v0, `draft`); còn 290 câu `pending_ai`. Prompt/guideline v1 chưa chạy thật |
| [04](phase-04-internal-contract-and-policies.md) | Runtime: hợp đồng dữ liệu, policy | Đã triển khai; PostgreSQL integration pass (`aprkb_test`) |
| [05](phase-05-protected-extraction-engines.md) | Runtime: trích slot bằng regex | Đã triển khai, thêm `extractability_reason`; unit và PostgreSQL integration pass |
| [06](phase-06-keying-and-worker-integration.md) | Runtime: key bảo thủ, nối worker; thêm `epistemic_tagger` theo luật | Đã triển khai; unit pass, PostgreSQL integration pass (`aprkb_test`) |
| [07](phase-07-gold-review-ui.md) | Màn hình duyệt gold trên web + API | Đã triển khai; web typecheck/lint pass, PostgreSQL integration pass (`aprkb_test`) |
| [08](phase-08-evaluator.md) | Đánh giá pipeline trên gold đã duyệt | Đã triển khai CLI/metric, tách `sentence_filter` và `extraction`; chưa chạy chính thức vì chưa có nhãn gold được duyệt |
| [09](phase-09-synonym-proposals.md) | Đề xuất từ đồng nghĩa | Hoãn |

Thứ tự: 01 → 02 → 03 → 07 (gán nhãn và duyệt có thể chạy trong lúc làm 04–06) → 04 → 05 → 06 → 08. Việc gọi Groq thật vẫn tắt cho tới khi owner xác nhận quyền xử lý AI bên ngoài; key/model đã được cấu hình. Evaluator chỉ chạy trên nhãn `approved`.

01 phải xong trước khi lấy mẫu: sửa tách câu làm thay đổi ranh giới câu, gold lập trước sẽ trỏ sai.

## Ràng buộc

- **Bản quyền:** câu gốc không vào git, không vào log, không vào audit. Gold lưu trong DB, tham chiếu câu bằng `article_id` + `char_start/char_end` + `text_sha256`. Báo cáo đánh giá chỉ chứa số liệu.
- **Quyền xử lý bởi AI bên ngoài:** `allows_mining` không đồng nghĩa được gửi cho bên thứ ba. Bản này chỉ cho gán nhãn khi `APP_ENV` là `local`/`test` (cùng cơ chế với `SLR_DEV_FALLBACK_LICENSE`). `TODO(owner, BR-10)`: quyết định quyền xử lý AI trước production.
- **AI không tự chốt:** nhãn AI có trạng thái `draft`. Evaluator chỉ đọc nhãn `approved`. Mọi lần duyệt ghi `reviewed_by`, `reviewed_at` và audit (không chứa câu).
- **Không chỉnh luật dựa trên phần đo:** khi lấy mẫu, gán ngẫu nhiên (seed cố định) 30% vào `split=test`. Viết luật chỉ xem `split=dev`; evaluator báo cáo riêng hai phần.
- **Phạm vi dữ liệu:** 6 bài, một lĩnh vực. Kết quả chỉ gọi là "gold dev v0", không dùng để khẳng định chất lượng production.
- Model, effort, phiên bản prompt và phiên bản hướng dẫn nằm trong `policies/gold_labeling.yaml`, giá trị tạm đánh dấu `TODO(owner)`.

## Owner cần làm

- **Cập nhật owner 2026-11-01:** Groq key chỉ nằm trong `.env` local để chạy thử có chủ đích. Không thêm UI nhập key, API lưu key, DB credential, mã hóa server-side, master key, rotation hay revoke trong giai đoạn dev. Không commit hoặc in key; chỉ dùng khi owner yêu cầu chạy Groq thật. `TODO(owner, BR-10)` vẫn áp dụng trước khi gửi câu chưa rõ quyền cho bên thứ ba.
- Chạy `bootstrap-key` để có key admin, và (sau phase 07) duyệt khoảng 300 nhãn trên web.
- Chi phí và giới hạn tốc độ phụ thuộc model Groq được chọn; đo bằng lần chạy thử ~10 câu trước khi chạy cả 300.

## Kiểm tra

TDD cho từng phase; unit test dùng fixture tự viết, LLM được giả lập bằng labeler giả (không gọi API thật trong test). `make lint`, `make test` với `TEST_DATABASE_URL` → `aprkb_test`, web typecheck + lint. Lần gọi LLM thật (Groq) chỉ chạy tay và báo cáo riêng.
