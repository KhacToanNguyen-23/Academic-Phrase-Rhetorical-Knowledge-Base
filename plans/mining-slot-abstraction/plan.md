# Plan: Mining slot abstraction + gold dev từ bài SLR thật

Ngày: 2026-11-01 (thay bản 2026-10-31)
Rủi ro: cao — gửi câu bài báo cho LLM bên ngoài (Groq), thêm bảng và migration, thêm màn hình web.
Trạng thái: chờ owner duyệt bản sửa đổi này.

## Thay đổi so với bản 2026-10-31

SLR import đã chạy được (4 bài thật, license `DEV-UNVERIFIED`), nên điều kiện "chờ API bài báo" đã đạt. Owner quyết định ngày 2026-11-01:

| Trước | Nay |
|---|---|
| Gold hoãn tới khi có API bài báo | Làm gold dev ngay, lấy mẫu khoảng 300 câu từ bài SLR thật |
| Hai editor gán nhãn độc lập, κ, phân xử (FR-06.6) | **LLM gán nhãn nháp, một người duyệt cuối.** Chỉ nhãn được duyệt mới là gold. Không báo cáo được κ: đây là lệch FR-06.6 có chủ đích |
| AI hỗ trợ là đề xuất, chưa có code | Tích hợp LLM vào hệ thống qua interface `GoldLabeler`; tạm dùng **Groq**, cấu hình trong policy YAML |
| Không thêm endpoint, không thêm màn hình | Thêm API `/v1/admin/gold/*` và màn hình duyệt gold trên web |

Không đổi: luồng runtime upload/import → ingest → `mine_article` → candidate `pending` → hai vòng review. Mining không ghi pattern/version. Gold **không** đi vào review queue và không tạo pattern.

## Phase

| Phase | Nội dung | Trạng thái |
|---|---|---|
| [01](phase-01-ingest-quality.md) | Chất lượng ingest: tách câu với chữ viết tắt, nhận diện section, lọc câu nhiễu | Đã code, chờ chạy `reingest` (cần Docker) |
| [02](phase-02-gold-schema-and-guideline.md) | Bảng gold, nhãn (Pydantic), hướng dẫn gán nhãn, lấy mẫu, cập nhật PRD/ADR | Chờ duyệt |
| [03](phase-03-llm-labeling.md) | Gán nhãn bằng LLM (tạm dùng Groq) qua job worker, validate bằng Pydantic | Chờ duyệt |
| [04](phase-04-internal-contract-and-policies.md) | Runtime: hợp đồng dữ liệu, policy | Đã duyệt G1, chưa làm |
| [05](phase-05-protected-extraction-engines.md) | Runtime: trích slot bằng regex | Đã duyệt G1, chưa làm |
| [06](phase-06-keying-and-worker-integration.md) | Runtime: key bảo thủ, nối worker; thêm `epistemic_tagger` theo luật | Đã duyệt G1, chưa làm |
| [07](phase-07-gold-review-ui.md) | Màn hình duyệt gold trên web + API | Chờ duyệt |
| [08](phase-08-evaluator.md) | Đánh giá pipeline trên gold đã duyệt | Chờ duyệt |
| [09](phase-09-synonym-proposals.md) | Đề xuất từ đồng nghĩa | Hoãn |

Thứ tự: 01 → 02 → 03 → 07 (gán nhãn và duyệt có thể chạy trong lúc làm 04–06) → 04 → 05 → 06 → 08.

01 phải xong trước khi lấy mẫu: sửa tách câu làm thay đổi ranh giới câu, gold lập trước sẽ trỏ sai.

## Ràng buộc

- **Bản quyền:** câu gốc không vào git, không vào log, không vào audit. Gold lưu trong DB, tham chiếu câu bằng `article_id` + `char_start/char_end` + `text_sha256`. Báo cáo đánh giá chỉ chứa số liệu.
- **Quyền xử lý bởi AI bên ngoài:** `allows_mining` không đồng nghĩa được gửi cho bên thứ ba. Bản này chỉ cho gán nhãn khi `APP_ENV` là `local`/`test` (cùng cơ chế với `SLR_DEV_FALLBACK_LICENSE`). `TODO(owner, BR-10)`: quyết định quyền xử lý AI trước production.
- **AI không tự chốt:** nhãn AI có trạng thái `draft`. Evaluator chỉ đọc nhãn `approved`. Mọi lần duyệt ghi `reviewed_by`, `reviewed_at` và audit (không chứa câu).
- **Không chỉnh luật dựa trên phần đo:** khi lấy mẫu, gán ngẫu nhiên (seed cố định) 30% vào `split=test`. Viết luật chỉ xem `split=dev`; evaluator báo cáo riêng hai phần.
- **Phạm vi dữ liệu:** 6 bài, một lĩnh vực. Kết quả chỉ gọi là "gold dev v0", không dùng để khẳng định chất lượng production.
- Model, effort, phiên bản prompt và phiên bản hướng dẫn nằm trong `policies/gold_labeling.yaml`, giá trị tạm đánh dấu `TODO(owner)`.

## Owner cần làm

- Cấp `GROQ_API_KEY` và chọn model Groq khi tới bước chạy thật của phase 03 (mình sẽ hỏi lúc đó); key chỉ nằm trong `.env` cục bộ.
- Chạy `bootstrap-key` để có key admin, và (sau phase 07) duyệt khoảng 300 nhãn trên web.
- Chi phí và giới hạn tốc độ phụ thuộc model Groq được chọn; đo bằng lần chạy thử ~10 câu trước khi chạy cả 300.

## Kiểm tra

TDD cho từng phase; unit test dùng fixture tự viết, LLM được giả lập bằng labeler giả (không gọi API thật trong test). `make lint`, `make test` với `TEST_DATABASE_URL` → `aprkb_test`, web typecheck + lint. Lần gọi LLM thật (Groq) chỉ chạy tay và báo cáo riêng.
