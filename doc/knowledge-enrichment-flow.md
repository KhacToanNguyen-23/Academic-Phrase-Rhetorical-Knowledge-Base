# Luồng làm giàu tri thức: từ bài báo đến pattern

Tài liệu này theo dõi trạng thái từng chức năng và thuật toán trong luồng
bài báo → câu → phrase → pattern đã duyệt. Trạng thái đối chiếu với code trên
nhánh `feat/scaffold-prd` ngày 2026-11-02. Khi một bước thay đổi trạng thái,
cập nhật bảng tương ứng trong cùng PR.

**Ký hiệu**

- [x] Đã chạy được và có test
- [~] Có một phần hoặc còn hạn chế đã biết
- [ ] Chưa làm (stub có `TODO(owner)` hoặc chưa có code)

## Tổng quan

```text
Bài báo ─[1. Import]──▶ articles, blob
        ─[2. Ingest]──▶ article_sections, sentences
        ─[3. Mining]──▶ lọc câu → mức độ → SLOT ABSTRACTOR
                        → chuẩn hóa → gom cụm → candidates (pending)
        ─[4. Review]──▶ 2 vòng duyệt → phrase_patterns, pattern_versions
        ─[5. Sử dụng]─▶ recommendation, validation

Đo chất lượng (nhánh riêng, không đi vào review queue):
  sentences ─[6. Gold dev]─▶ mẫu 300 câu → Groq gán nhãn nháp → người duyệt
            ─▶ eval-mining: sentence_filter | extraction
```

Slot abstractor là ranh giới giữa "câu" và "phrase". Các stage trước nó xử lý
câu. Các stage sau nó xử lý khung phrase.

## 1. Lấy bài báo (import)

Mã nguồn: `apps/backend/src/aprkb/modules/corpus/importer.py`, `sources/`,
web: `apps/web/src/features/slr-import/`.

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | 1.1 Admin tạo import profile (bộ lọc, loại artifact, `batch_limit`) rồi gọi `POST /v1/admin/corpus/imports` để tạo job `import_articles` | `import_profiles`, `jobs` | Trả 409 nếu nguồn là `null` |
| [~] | 1.2 Worker gọi `SlrArticleSource` (`sources/slr_source.py`) lấy bài từ SLR Repository API | — | **SLR không trả license.** Bài không có license bị bỏ qua (fail closed). Ở `APP_ENV` local/test, `SLR_DEV_FALLBACK_LICENSE` gán license `DEV-UNVERIFIED` để chạy thử. `TODO(owner, PRD-04, BR-10)`: owner quyết định trước production |
| [x] | 1.3 Kiểm tra license `allows_mining`, định dạng, trùng `external_id`/DOI **trước khi tải nội dung** | — | |
| [x] | 1.4 `fetch_content` tải nội dung (giới hạn kích thước, kiểm tra checksum) rồi lưu blob | `data/blobs` | Xóa blob nếu giao dịch lỗi |
| [~] | 1.5 Tạo bài báo và job `ingest_article`, ghi audit `corpus.import.page` | `articles`, `jobs`, `audit_events` | **Chưa điền `journal_id`/`genre_id`** và chưa lưu metadata journal từ SLR |
| [x] | 1.6 Còn `next_cursor` thì tạo job import tiếp theo, giữ nguyên bộ lọc và loại artifact | `jobs` | |
| [ ] | 1.7 Giới hạn **tổng** số bài (`max_articles`) | — | `batch_limit` chỉ giới hạn mỗi trang. Job tiếp theo vẫn import toàn bộ kết quả lọc, không có cách dừng |
| [~] | 1.8 Bộ lọc theo lĩnh vực, topic, journal/ISSN, năm, ngôn ngữ, loại xuất bản | `import_profiles.filters` | `SlrWorkFilters` kiểm tra các trường SLR hỗ trợ, màn hình web `/import` có form. `TODO(owner, PRD-04)`: chưa xác nhận giá trị hợp lệ của `language`/`publicationType` |
| [x] | 1.9 Số đếm kết quả mỗi trang (nhập, bỏ qua, lý do) | `jobs.result` | |
| [ ] | 1.10 Hủy job import đang chạy | — | |

Đường thay thế: upload tay qua `POST /v1/admin/corpus/articles`. Đường này đi
thẳng tới bước 1.5 và đã chạy được.

## 2. Tách bài báo (ingest)

Mã nguồn: `apps/backend/src/aprkb/worker/handlers.py` (`_ingest`), `modules/corpus/`.

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | 2.1 Kiểm tra lại license **trước khi đọc blob** | `articles.ingest_status = rejected` nếu không có quyền | |
| [x] | 2.2a Parser `.txt` | — | `parsers/text_parser.py` |
| [x] | 2.2b Parser `.md` | — | `parsers/markdown_parser.py` |
| [ ] | 2.2c Parser PDF | — | Stub, `TODO(owner, FR-07)`: kết nối GROBID. PDF được lưu nhưng ingest báo lỗi |
| [ ] | 2.2d Parser JATS XML | — | Stub |
| [x] | 2.3 `SectionDetector`: gắn mã section (`ABSTRACT`, `INTRO`, `RELATED_WORK`, `METHODS`, `RESULTS`, `DISCUSSION`, `CONCLUSION`, hoặc mã không thuộc tu từ như `REFERENCES`, `BACK_MATTER`, `FIGURES_TABLES`, `APPENDIX`) | `article_sections.section_code` | Ánh xạ tiêu đề qua `policies/section_headings.yaml`. Tiểu mục (`3.1`) kế thừa section cha; số đầu mục chỉ tính khi nối tiếp thứ tự. Section không nhận ra là `NULL` |
| [x] | 2.4 `split_sentences`: tách câu, giữ vị trí ký tự | `sentences` | Không cắt sau chữ viết tắt trong `policies/lexicon/abbreviations.yaml`, chữ cái hoa đứng một mình, hoặc khi ký tự kế tiếp là chữ thường. Ngắt đoạn (hai xuống dòng trở lên) luôn kết thúc câu. Trên 4 bài SLR, số câu giảm 771→730, 705→647, 96→85, 1288→1276 |
| [x] | 2.5 Đặt `ingest_status = ready` | `articles` | |
| [x] | 2.6 Ingest lại bài đã nhập: `python -m aprkb.cli reingest --source slr` | `sentences`, `article_sections` | Cần chạy lại khi đổi luật tách câu hoặc section. `gold_items` giữ `text_sha256`, lệch thì đánh dấu `stale` |

## 3. Mining (job `mine_article`)

Mã nguồn: `apps/backend/src/aprkb/modules/mining/stages/`, `worker/handlers.py` (`_mine`).
Kích hoạt: `POST /v1/admin/corpus/articles/{id}/mine`. Chưa tự động chạy sau ingest.

Thứ tự stage (`stages/__init__.py`): `sentence_filter` → `move_classifier` →
`epistemic_tagger` → `slot_abstractor` → `frame_normalizer` → `clusterer` →
`dedup_matcher`.

Ví dụ xuyên suốt (câu tự viết, lấy từ test): *"Our results suggest that the
pilot filter improves retrieval quality [12]."* → khung `[X] [Y] suggest that [Z].`

| Trạng thái | Stage | Làm gì | Trường kết quả | Ví dụ |
|---|---|---|---|---|
| [x] | 3.1 `sentence_filter` | Giữ câu 5–60 từ (`policies/mining_filter.yaml`); đếm từ không tính trích dẫn `[1]`/`(Smith, 2020)`. Nội dung câu **không** bị sửa; trích dẫn trong slot được gắn tín hiệu bảo vệ ở stage sau | — | Giữ câu |
| [~] | 3.1b Loại câu nhiễu | Lý do loại: `excluded_section`, `table_row`, `caption`, `math`, `numeric`, `length` | — | **Bộ lọc cơ bản, chưa tinh chỉnh.** Ngưỡng tạm `TODO(owner, PRD-6.3)`. Chưa bắt được mảnh câu (`fragment`), metadata, lời cảm ơn ngoài section loại. Trên mẫu thử 10 câu, bộ lọc chưa loại được câu nhiễu nào |
| [ ] | 3.2 `move_classifier` | Câu thực hiện chức năng tu từ nào | `intent_id` | Stub `TODO(owner, FR-06.3)` |
| [~] | 3.3 `epistemic_tagger` | Mức khẳng định theo từ đánh dấu trong `policies/lexicon/epistemic_markers.yaml` | `epistemic_strength` | *suggest* → `moderate`. Danh sách từ **là bản nháp** (`TODO(owner, FR-06.2)`), thiếu *argue*, *clearly*… Trả giá trị chỉ khi đúng một mức xuất hiện; bỏ qua từ đứng sau phủ định |
| [~] | **3.4 `slot_abstractor`** | **Câu → khung phrase** bằng regex: động từ báo cáo + *that*. Chủ ngữ tối đa 8 từ, mệnh đề tối thiểu 2 từ. Tách slot `X`/`Y`/`Z`, gán tense, ownership (own/prior/unclear theo determiner), tín hiệu bảo vệ (số, phủ định, tình thái, so sánh…) | `slots`, `occurrences`, `tense`, `ownership` | `[X] [Y] suggest that [Z].` **Chỉ nhận mẫu hẹp.** `extractability_reason(text)` cho biết vì sao một câu không trích được: `no_reporting_verb`, `no_that`, `no_subject`, `subject_too_long`, `clause_too_short`. Trên 10 nhãn nháp, 1/7 câu sạch trích được, phần lớn do `no_reporting_verb` (chưa phải kết quả đánh giá) |
| [~] | 3.5 `frame_normalizer` | Chỉ chuẩn hóa khoảng trắng | `text` | **Chưa chuẩn hóa từ đồng nghĩa** (phase 09 hoãn; lexicon do người duyệt) |
| [x] | 3.6 `clusterer` | Tạo `cluster_key` bảo thủ từ khung, lớp động từ báo cáo, tense, mức khẳng định, kiểu slot. **Khác thì động từ thì khác cụm** | `cluster_key` | Không gom theo ngữ nghĩa |
| [ ] | 3.7 `dedup_matcher` | So với pattern đã có | `matched_pattern_id` | Stub `TODO(owner, FR-06.2)` |
| [ ] | 3.8 Độ tin cậy | Điểm tin cậy cho reviewer | `confidence` | Luôn `null` |
| [x] | 3.9 `CandidateWriter` | Ghi candidate chờ duyệt, không ghi thẳng vào pattern. **Từ chối khung chưa che slot**, thiếu `source_sentence_ids` hoặc slot sai kiểu | `candidates` (`status = pending`), `source_sentence_ids`, vị trí nguồn riêng tư | Migration 0005 lưu offset nguồn của từng lần xuất hiện, không lưu văn bản |

> **Hạn chế hiện tại:** chỉ câu khớp mẫu "động từ báo cáo + *that*" mới thành
> candidate (đã là khung che slot, không còn là câu nguyên văn). Các câu sạch
> khác bị bỏ ở 3.4. Mở rộng danh sách động từ hoặc mẫu không có *that* chờ số
> liệu từ gold được duyệt.

## 4. Duyệt và lưu thành tri thức

Mã nguồn: `apps/backend/src/aprkb/modules/review/`.

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | 4.1 Reviewer xem hàng chờ `GET /v1/admin/review-queue` | — | Candidate cũ có khung chưa che slot bị từ chối khi duyệt (409) |
| [x] | 4.2 Duyệt vòng 1: `POST /v1/admin/review-queue/{id}/decisions` | `review_decisions`, `audit_events` | Reject ở bất kỳ vòng nào → `rejected` |
| [x] | 4.3 Duyệt vòng 2. Cả hai vòng approve → `accepted` | `review_decisions` | |
| [~] | 4.4 Bắt buộc hai reviewer khác nhau | — | Chưa quyết định. Hiện một người có thể duyệt cả hai vòng |
| [x] | 4.5 Thăng hạng thành pattern | `phrase_patterns`, `pattern_versions` (chỉ thêm, không sửa), `audit_events` | |
| [ ] | 4.6 AI gợi ý nhãn cho **candidate** để reviewer chỉ xác nhận | — | AI hiện chỉ gán nhãn cho **gold dev** (mục 6), chưa dùng ở review queue |

## 5. Sử dụng tri thức

| Trạng thái | Chức năng | Endpoint |
|---|---|---|
| [x] | Gợi ý phrase có giải thích điểm và fallback tier | `POST /v1/recommendations` |
| [x] | Kiểm tra câu (V01–V08, V02 dùng chung `EvidencePolicy`) | `POST /v1/validate` |

## 6. Gold dev và đánh giá chất lượng

Mã nguồn: `modules/gold/`, `modules/mining/evaluation.py`, web `apps/web/src/features/gold/`
(trang `/gold`). Tài liệu: `eval/mining/gold/` (GUIDELINE v1, FORMAT, DEV_PROTOCOL,
ANNOTATION_STATUS), `doc/adr/0008-gold-dev-labeling.md`, `plans/mining-slot-abstraction/`.

Quy trình gold dev (quyết định của owner): **AI gán nhãn nháp mọi câu, một người
duyệt cuối**. Không có editor thứ hai, không tính κ, không đáp ứng yêu cầu validation
hai editor của FR-06.6. Gold lưu tham chiếu câu (`article_id`, offset, `text_sha256`),
không lưu văn bản; chỉ nhãn `approved` mới tính là gold.

| Trạng thái | Việc | Ghi chú |
|---|---|---|
| [x] | 6.1 Unit test các stage bằng dữ liệu mock tự viết | Áp dụng cho mọi stage mới |
| [x] | 6.2 Bảng `gold_items`, API `/v1/admin/gold/*`, trang duyệt `/gold` | Trạng thái: `pending_ai` → `draft` → `approved`/`rejected`; ngoài ra `label_failed`, `stale` |
| [x] | 6.3 Lấy mẫu 300 câu từ bài SLR, phân tầng theo section, 10% từ câu bị bộ lọc loại, 90 câu `test` chọn riêng trong từng tầng | `policies/gold_sampling.yaml`. Xóa batch: `delete-gold-batch` |
| [x] | 6.4 Guideline v1: định nghĩa từng nhãn, ví dụ tự viết, quy tắc `frame` | `keep` = câu là văn xuôi sạch, **không** nghĩa là trích được slot. Test chống lệch với YAML từ đánh dấu |
| [~] | 6.5 Groq gán nhãn nháp (`openai/gpt-oss-120b`, JSON schema strict) | Đã chạy thử 10/300 câu bằng prompt v0 (10/10 thành công, ~2,2 nghìn token/câu). Còn 290 câu `pending_ai`. Dừng và giữ nhãn đã gán khi hết quota. Chỉ chạy khi `APP_ENV` local/test và owner bật cờ; `TODO(owner, BR-10)` |
| [x] | 6.6 Kiểm tra tự động nhãn AI: frame phải bằng câu với mỗi slot thay bằng `[tên]` | Lệch → `label_failed`. Rà tay mẫu 10 câu thấy 3/7 câu `keep=true` lệch, là lý do thêm kiểm tra |
| [ ] | 6.7 Người duyệt nhãn trên `/gold` | Chưa có nhãn `approved`. 10 nhãn v0 hiện có không nên duyệt thẳng; gán lại bằng v1 |
| [x] | 6.8 Evaluator `eval-mining`, tách hai chỉ số | `sentence_filter` (keep, so lý do nhiễu bằng bảng nhầm lẫn thô) và `extraction` (coverage, lý do không trích, accuracy và slot F1 trên câu đã trích) |
| [ ] | 6.9 Chạy `eval-mining --split dev` / `--split test` và đọc kết quả | Chờ nhãn gold được duyệt. Chưa có kết luận chất lượng nào |

## Thứ tự đề xuất

Đã xong: import SLR có profile và bộ lọc, tách câu với chữ viết tắt, nhận diện
section, lọc nhiễu cơ bản, `epistemic_tagger`, `slot_abstractor`, `frame_normalizer`,
`clusterer`, hạ tầng gold dev và evaluator.

1. Gán nhãn lại bằng prompt/guideline v1 (thử 10 câu, rồi chia 290 câu còn lại theo hạn mức ngày của Groq).
2. Người duyệt nhãn trên `/gold` (6.7), rồi chạy `eval-mining` (6.9).
3. Dựa trên số liệu: mở rộng danh sách động từ báo cáo hoặc mẫu không có *that* (3.4), chốt danh sách từ đánh dấu (3.3), tinh chỉnh bộ lọc nhiễu (3.1b).
4. `move_classifier` (3.2), `dedup_matcher` (3.7), độ tin cậy (3.8).
5. Import: `max_articles` (1.7), hủy job (1.10), metadata journal/genre (1.5), quyết định license với SLR (1.2).
6. PDF parser (2.2c) nếu đối tác trả PDF.
7. AI hỗ trợ duyệt candidate (4.6) sau khi các stage luật có số liệu.
