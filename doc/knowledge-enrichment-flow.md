# Luồng làm giàu tri thức: từ bài báo đến pattern

Tài liệu này theo dõi trạng thái từng chức năng và thuật toán trong luồng
bài báo → câu → phrase → pattern đã duyệt. Trạng thái đối chiếu với code trên
nhánh `feat/scaffold-prd` ngày 2026-10-31. Khi một bước thay đổi trạng thái,
cập nhật bảng tương ứng trong cùng PR.

**Ký hiệu**

- [x] Đã chạy được và có test
- [~] Có một phần hoặc còn hạn chế đã biết
- [ ] Chưa làm (stub có `TODO(owner)` hoặc chưa có code)

## Tổng quan

```text
Bài báo ─[1. Import]──▶ articles, blob
        ─[2. Ingest]──▶ article_sections, sentences
        ─[3. Mining]──▶ lọc câu → chức năng → mức độ → SLOT ABSTRACTOR
                        → chuẩn hóa → gom cụm → so trùng → candidates (pending)
        ─[4. Review]──▶ 2 vòng duyệt → phrase_patterns, pattern_versions
        ─[5. Sử dụng]─▶ recommendation, validation
```

Slot abstractor là ranh giới giữa "câu" và "phrase". Các stage trước nó xử lý
câu. Các stage sau nó xử lý khung phrase.

## 1. Lấy bài báo (import)

Mã nguồn: `apps/backend/src/aprkb/modules/corpus/importer.py`, `sources/`.

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | 1.1 Admin gọi `POST /v1/admin/corpus/imports` để tạo job `import_articles` | `jobs` | Trả 409 nếu nguồn là `null` |
| [~] | 1.2 Worker gọi `ArticleSource.list_articles(cursor, limit)` | — | Chỉ có `NullArticleSource`. **Chưa có HTTP adapter** (chờ tài liệu API của đối tác, PRD-04) |
| [x] | 1.3 Kiểm tra định dạng, license `allows_mining`, trùng `external_id`/DOI **trước khi tải nội dung** | — | |
| [x] | 1.4 `fetch_content` tải nội dung rồi lưu blob | `data/blobs` | Xóa blob nếu giao dịch lỗi |
| [~] | 1.5 Tạo bài báo và job `ingest_article`, ghi audit `corpus.import.page` | `articles`, `jobs`, `audit_events` | **Chưa điền `journal_id`/`genre_id`**: `SourceArticleRef` không có trường này |
| [x] | 1.6 Còn `next_cursor` thì tạo job import tiếp theo | `jobs` | |
| [ ] | 1.7 Giới hạn tổng số bài (`max_articles`) | — | Hiện tại job tiếp theo import **toàn bộ** nguồn, không có cách dừng |
| [ ] | 1.8 Bộ lọc journal/ISSN, genre, lĩnh vực, năm, ngôn ngữ | — | Phụ thuộc tham số mà API đối tác hỗ trợ |
| [ ] | 1.9 Hủy job import đang chạy | — | |

Đường thay thế: upload tay qua `POST /v1/admin/corpus/articles`. Đường này đi
thẳng tới bước 1.5 và đã chạy được.

## 2. Tách bài báo (ingest)

Mã nguồn: `apps/backend/src/aprkb/worker/handlers.py` (`_ingest`), `modules/corpus/`.

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | 2.1 Kiểm tra lại license **trước khi đọc blob** | `articles.ingest_status = rejected` nếu không có quyền | |
| [x] | 2.2a Parser `.txt` | — | `parsers/text_parser.py` |
| [x] | 2.2b Parser `.md` | — | `parsers/markdown_parser.py` |
| [ ] | 2.2c Parser PDF | — | Stub, `TODO(owner, FR-07)`: kết nối GROBID |
| [ ] | 2.2d Parser JATS XML | — | Stub |
| [ ] | 2.3 `detect_section`: gắn loại section (Introduction/Methods/Results/Discussion) | `article_sections.section_code` | Stub, luôn trả `None`. Đề xuất: ánh xạ tiêu đề section qua YAML policy |
| [~] | 2.4 `split_sentences`: tách câu theo ngữ cảnh dấu câu và chữ viết tắt, giữ vị trí ký tự | `sentences` | Bổ sung mock regression cho `e.g.`, `i.e.`, `et al.`, `Fig.`, `Dr.`, dấu ngoặc/nháy và offsets. Vẫn là heuristic cho văn bản học thuật tiếng Anh, chưa đo trên gold |
| [x] | 2.5 Đặt `ingest_status = ready` | `articles` | |

## 3. Mining (job `mine_article`)

Mã nguồn: `apps/backend/src/aprkb/modules/mining/stages/`, `worker/handlers.py` (`_mine`).
Kích hoạt: `POST /v1/admin/corpus/articles/{id}/mine`. Chưa tự động chạy sau ingest.

Ví dụ xuyên suốt: *"These findings suggest that soil salinity reduces rice yield."*

| Trạng thái | Stage | Làm gì | Trường kết quả | Ví dụ |
|---|---|---|---|---|
| [~] | 3.1 `sentence_filter` | Bỏ trích dẫn `[1]`/`(Smith, 2020)`, giữ câu 5–60 từ (`policies/mining_filter.yaml`) | `text` | Giữ câu |
| [ ] | 3.1b Loại câu nhiễu | Chú thích hình, dòng bảng, công thức, câu nhiều số, lời cảm ơn | — | Chưa có. Hiện bộ lọc chỉ xét độ dài |
| [ ] | 3.2 `move_classifier` | Câu thực hiện chức năng tu từ nào | `intent_id` | *interpreting results* |
| [ ] | 3.3 `epistemic_tagger` | Mức độ khẳng định (hedge/boost) | `epistemic_strength` | *suggest* → hedged |
| [ ] | **3.4 `slot_abstractor`** | **Câu → khung phrase**: giữ phần tu từ, thay nội dung chuyên ngành bằng slot | `canonical_frame`, `slots` | *These findings suggest that [X] [VERB] [Y].* |
| [ ] | 3.5 `frame_normalizer` | Chuẩn hóa biến thể: chữ hoa/thường, từ đồng nghĩa **cùng thì, cùng mức độ** | `canonical_frame` | |
| [ ] | 3.6 `clusterer` | Gom khung giống nhau. **Khác thì động từ thì khác cụm** | `cluster_key` | |
| [ ] | 3.7 `dedup_matcher` | So với pattern đã có | `matched_pattern_id` | |
| [ ] | 3.8 Độ tin cậy | Điểm tin cậy cho reviewer | `confidence` | Hiện luôn `null` |
| [x] | 3.9 `CandidateWriter` | Ghi candidate chờ duyệt, không ghi thẳng vào pattern | `candidates` (`status = pending`), `source_sentence_ids` | |

> **Hạn chế hiện tại:** vì 3.2–3.7 còn là stub, bước 3.9 đang ghi **nguyên văn
> câu gốc** vào `canonical_frame`. Candidate lúc này là câu trích từ bài báo,
> chưa phải phrase. Slot abstractor (3.4) là bước sửa hạn chế này.

## 4. Duyệt và lưu thành tri thức

Mã nguồn: `apps/backend/src/aprkb/modules/review/`.

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | 4.1 Reviewer xem hàng chờ `GET /v1/admin/review-queue` | — | |
| [x] | 4.2 Duyệt vòng 1: `POST /v1/admin/review-queue/{id}/decisions` | `review_decisions`, `audit_events` | Reject ở bất kỳ vòng nào → `rejected` |
| [x] | 4.3 Duyệt vòng 2. Cả hai vòng approve → `accepted` | `review_decisions` | |
| [~] | 4.4 Bắt buộc hai reviewer khác nhau | — | Chưa quyết định. Hiện một người có thể duyệt cả hai vòng |
| [x] | 4.5 Thăng hạng thành pattern | `phrase_patterns`, `pattern_versions` (chỉ thêm, không sửa), `audit_events` | |
| [ ] | 4.6 AI gợi ý nhãn (intent, mức độ, độ tin cậy) để reviewer chỉ xác nhận | — | Hướng đã thống nhất: AI gợi ý, người quyết định. Làm sau khi các stage luật chạy được |

## 5. Sử dụng tri thức

| Trạng thái | Chức năng | Endpoint |
|---|---|---|
| [x] | Gợi ý phrase có giải thích điểm và fallback tier | `POST /v1/recommendations` |
| [x] | Kiểm tra câu (V01–V08, V02 dùng chung `EvidencePolicy`) | `POST /v1/validate` |

## 6. Đánh giá chất lượng thuật toán

| Trạng thái | Việc | Ghi chú |
|---|---|---|
| [x] | Unit test các stage bằng dữ liệu mock tự viết | Áp dụng cho mọi stage mới |
| [ ] | Bộ gold trên câu từ bài báo thật | Chờ API bài báo. Hai editor gán nhãn độc lập, có bước phân xử (FR-06.6) |
| [ ] | Đo độ chính xác từng stage trên gold | Chờ bộ gold |

## Thứ tự đề xuất

Các bước 1–4 dưới đây chạy được bằng dữ liệu mock, không cần gold hay API đối tác.

1. Import: `max_articles`, khung bộ lọc, metadata journal/genre (1.5, 1.7, 1.8), test bằng mock source.
2. Sửa tách câu với chữ viết tắt (2.4).
3. Nhận diện section (2.3).
4. Loại câu nhiễu (3.1b).
5. `move_classifier` → `epistemic_tagger` → `slot_abstractor` (3.2–3.4).
6. `frame_normalizer` → `clusterer` → `dedup_matcher` (3.5–3.7).
7. Khi có tài liệu API: HTTP adapter (1.2), PDF parser nếu đối tác trả PDF (2.2c).
8. Khi có bài báo thật: bộ gold và đo chất lượng (mục 6), rồi AI hỗ trợ duyệt (4.6).

## Phạm vi sửa tách câu (2026-11-02)

Task tách câu nằm ở bước 2.4, trước mining; không thay thế bước 3.4 tạo
khung phrase. Kiểm thử bằng văn bản mock tự viết, giữ nguyên `SentenceSpan`
và offsets để worker tiếp tục truy nguồn tới bài báo. Không cần tải model NLP.

Theo phân công của nhóm, bộ gold do phần slot abstractor phụ trách; không tạo
bộ gold mới trong task này. Checkout hiện tại chỉ có ví dụ synthetic trong
`eval/mining/`, vì vậy mock test không được coi là điểm chất lượng trên gold.

Giới hạn: các chữ viết tắt dạng tiền tố (`Dr.`, `Fig.`, `e.g.`) được giữ
liền với phần sau; chữ cái đầu/từ viết tắt như `U.S.` dùng một danh sách
hữu hạn các từ mở đầu câu để nhận diện ranh giới. Những ngữ cảnh mơ hồ ngoài
các quy tắc này vẫn cần đối chiếu trên dữ liệu thật trước khi mở rộng.
