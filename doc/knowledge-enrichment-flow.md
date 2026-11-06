# Luồng làm giàu tri thức: từ bài báo đến pattern

Tài liệu này theo dõi trạng thái từng chức năng và thuật toán trong luồng
bài báo → câu → phrase → pattern đã duyệt. Trạng thái chức năng đối chiếu với
code hiện tại từ nền `dev` tại `4149e7f` ngày 2026-11-04. Các số liệu thử nghiệm/gold ở mục 3
và 6 là snapshot ngày 2026-11-02, không phải số đếm DB hiện tại. Khi một bước
thay đổi trạng thái, cập nhật bảng tương ứng trong cùng PR.

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
                        ├─[4A. Review API]─▶ 2 vòng duyệt + intent đã có
                        │                    → phrase_patterns, pattern_versions
                        │                    ─[5. Online]─▶ recommendation, render, validation
                        └─[4B. /extract]───▶ 1 người duyệt → approved_phrases
                                             → đầu vào fingerprint (chưa làm)

Chuyển tri thức Offline → Online (mục 7):
  graph pattern đủ điều kiện → export-pack → validate-pack → import-pack
                            → phrase_patterns, pattern_versions → [5. Online]
  approved_phrases không nằm trong pack và không đi vào recommendation.

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
Kích hoạt từng bài: `POST /v1/admin/corpus/articles/{id}/mine`, hoặc theo phạm vi
bài/batch qua `POST /v1/admin/corpus/mine` từ `/extract`. Chưa tự động chạy sau ingest.

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

### 4A. Hai vòng duyệt để tạo pattern

Mã nguồn: `apps/backend/src/aprkb/modules/review/`. Hàng chờ này chưa có UI riêng.

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | 4.0 Reviewer gán intent qua `PUT /v1/admin/review-queue/{id}/intent` với `intent_id` | `candidates`, `audit_events` | Intent phải thuộc taxonomy đã publish; chỉ sửa khi pending, trước vòng duyệt đầu. Candidate cũ đã có vòng 1 approve nhưng chưa có intent: chỉ reviewer vòng 1 được gán và xác nhận intent, có audit riêng |
| [x] | 4.1 Reviewer xem hàng chờ `GET /v1/admin/review-queue` | — | Candidate cũ có khung chưa che slot bị từ chối khi duyệt (409) |
| [x] | 4.2 Duyệt vòng 1: `POST /v1/admin/review-queue/{id}/decisions` | `review_decisions`, `audit_events` | Approve thiếu intent → 409 trước khi ghi quyết định; reject ở bất kỳ vòng nào → `rejected` |
| [~] | 4.3 Duyệt vòng 2. Cả hai vòng approve → `accepted` nếu thăng hạng thành công | `review_decisions` | Thiếu intent hoặc provenance hợp lệ → 409, rollback quyết định vòng 2 |
| [~] | 4.4 Bắt buộc hai reviewer khác nhau | — | Chưa quyết định. Hiện một người có thể duyệt cả hai vòng |
| [x] | 4.5 Thăng hạng thành pattern sau hai approve | `phrase_patterns`, `pattern_versions` (chỉ thêm, không sửa), `audit_events` | Cần intent đã gán ở 4.0 và provenance hợp lệ. Test tích hợp đi từ upload → ingest → mining → gán intent qua API → hai approve → Online read/render; không gán intent trực tiếp trong DB nữa |
| [ ] | 4.6 AI gợi ý nhãn cho **candidate** để reviewer chỉ xác nhận | — | AI hiện chỉ gán nhãn cho **gold dev** (mục 6), chưa dùng ở review queue |

Pattern được thăng hạng hiện có `claim_type = unknown`; không tự suy ra nhãn chỉ
để đủ điều kiện xuất pack. Hai vòng duyệt lưu quyết định theo candidate; exporter
đọc được chúng cho version 1, không tái sử dụng cho version chỉnh sửa (mục 7).
Chưa có UI riêng cho hàng chờ 4A: dùng API qua `/docs`, lấy ID intent từ taxonomy
đã publish. API này phục vụ tác vụ Offline; không trỏ session ghi vào DB Online.

### 4B. Một người duyệt trên `/extract`

Mã nguồn: `apps/backend/src/aprkb/modules/extraction/`, web
`apps/web/src/features/phrase-extraction/`. Quyết định: [ADR-0009](adr/0009-phrase-extraction-page.md).

| Trạng thái | Bước | Ghi xuống DB | Ghi chú |
|---|---|---|---|
| [x] | Xem batch import, chọn nhiều batch/bài và xếp job mining | `jobs` | Batch là một lần import; bài cũ không có batch được nhóm riêng |
| [x] | Xem text bài và phrase cạnh nhau, accept/reject từng phrase hoặc hàng loạt | `candidates`, `approved_phrases`, `audit_events` | Một reviewer; accept kiểm tra lại quyền mining và schema khung/slot |
| [x] | Accept phrase không cần intent | `approved_phrases` (chỉ thêm), candidate → `accepted` | Không tạo `PhrasePattern`, không vào Library/recommendation hoặc pack. Candidate đã accept rời hàng chờ 4A |
| [ ] | Dùng approved phrase tạo fingerprint journal | — | Chưa có fingerprint; journal của bài/phrase có thể còn null |

## 5. Sử dụng tri thức

| Trạng thái | Chức năng | Endpoint | Giới hạn hiện tại |
|---|---|---|---|
| [x] | Đọc pattern hiện hành đã approve qua hợp đồng Online chung | `GET /v1/patterns`, detail/version | Nhãn `unknown` trả null và cờ `labelled=false`; không trả source text |
| [~] | Gợi ý phrase có giải thích điểm và fallback tier | `POST /v1/recommendations` | Khi chọn journal, chỉ trả pattern mined đã approve có provenance bài thuộc journal đó; không có mapping thì trả rỗng, không fallback. Chưa có fingerprint hoặc discipline ranking. Không chọn journal thì dùng fallback tier generic. Có gate `evidence_min` và `forbidden_contexts` (so mã literal section/genre/claim type, chờ owner chốt semantics) |
| [x] | Render phrase với slot của người viết | `POST /v1/render` | Cần recommendation đã cấp cho cùng client; kiểm tra slot bắt buộc/độ dài tối thiểu |
| [~] | Kiểm tra câu, giữ hợp đồng kết quả V01–V08 | `POST /v1/validate` | V02 kiểm tra claim/evidence bằng `EvidencePolicy`; V03 kiểm tra grounding giới hạn; V06 dò cụm từ style cấu hình, không kiểm tra ngữ pháp. V05 là `not_applicable` vì luồng Writer kiểm tra câu, không kiểm tra tuân thủ guideline journal/toàn bản thảo. V01/V04/V07/V08 vẫn `unavailable`, không phải pass |

Hai lỗi metadata đã sửa trên nền `dev`: Online ưu tiên `source_sentence_count`
được import, fallback sang số sentence ID cục bộ khi count là null; tạo version
mới giữ `evidence_min`, `forbidden_contexts`, sentence count, source section và
occurrence hash của version trước. Đây không phải triển khai thêm thuật toán mining.

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

## 7. Chuyển pattern Offline → Online bằng data pack

Mã nguồn: `apps/backend/src/aprkb/modules/pack/`. Hợp đồng:
[data-pack-spec.md](data-pack-spec.md), schema
`packages/contracts/data-pack/pack.schema.json`.

| Trạng thái | Bước | Giới hạn hiện tại |
|---|---|---|
| [x] | `validate-pack <directory>` kiểm tra manifest/hash, taxonomy, enum, slot, license, provenance và review | Chạy không cần DB; pack dùng natural key, không mang text nguồn hay article/sentence UUID |
| [x] | `export-pack --out <directory> --only-approved` | Chuẩn hóa bracket/typed slot và count từ sentence IDs; đọc review candidate cho version 1. Kiểm tra toàn bộ graph bằng cùng validator như import. Pattern không hợp lệ bị loại với ID/mã lỗi/path rõ ràng ở stderr; cần kiểm tra số lượng được xuất và bị loại |
| [x] | `init-reference`, `import-pack <directory> --dry-run`, rồi `import-pack <directory>` trên DB thử nghiệm/staging | Import transactional/idempotent và bảo vệ version đã lưu. Test DB cô lập kiểm tra graph đủ nhãn + review → export → validate → import sạch → reimport không đổi → re-export giữ nội dung; sửa version đã biết bị E15 |

Mined pack cần license cho phép mining (không phải `DEV-UNVERIFIED`), article
natural key, sentence count dương, hai vòng approve có reviewer/role/time, nhãn
claim/strength hợp lệ và placeholder `{slot}`. Exporter chuyển `[slot]` thành
`{slot}` khi schema khớp, bỏ metadata slot `signals` nội bộ, lấy count từ provenance
hoặc sentence IDs, và chỉ xuất danh tính/vai trò/thời gian của reviewer nội bộ
(không mang comment có thể chứa text nguồn). Review của pack đã import giữ metadata
riêng để round-trip không đổi. File xuất ghi đúng byte UTF-8 dùng tính SHA-256, kể
cả trên Windows.

**Còn thiếu:** promotion thông thường vẫn tạo `claim_type = unknown`; các pattern
này bị loại với E05. Không tự gán nhãn hoặc tái dùng approve của version 1 cho
version mới để ép xuất pack. `approved_phrases` vẫn không thuộc graph được xuất.
Vì vậy tooling chuyển graph hợp lệ đã có test, nhưng mining không tự tạo ra pack
đủ nhãn cho mọi candidate.

Sau mỗi export, chạy `validate-pack` và kiểm tra số lượng pattern/version trước
khi import. Không bỏ gate license, nhãn hay review để ép pack hợp lệ.

DB đang phục vụ Online chỉ được query trong workflow này. `export-pack` là thao
tác đọc; `init-reference`/`import-pack` có ghi nên không chạy trên DB Online đang
hoạt động. Chỉ kiểm thử các lệnh ghi trên DB Offline/staging/test tách biệt; việc
cấp dữ liệu cho Online cần quy trình riêng. Các module dùng chung session nên phân
tách deployment/quyền DB phải được cấu hình bên ngoài, không do tên endpoint bảo đảm.

## Thứ tự đề xuất

Đã xong: import SLR có profile và bộ lọc, tách câu với chữ viết tắt, nhận diện
section, lọc nhiễu cơ bản, `epistemic_tagger`, `slot_abstractor`, `frame_normalizer`,
`clusterer`, hạ tầng gold dev và evaluator.

Đã nối export với metadata/review version 1 và thêm test round-trip (mục 7);
reviewer có thể gán intent trước duyệt (4.0). Việc tiếp theo cho pack: quy trình
người duyệt gán claim type/strength đầy đủ và review riêng cho version mới, không
tự suy đoán nhãn hay tái dùng approval. Không đổi 4B thành pattern approval nếu
chưa có quyết định thay thế ADR-0009.

Thứ tự cho nhánh cải thiện chất lượng mining (số lượng gold cần kiểm tra lại trong DB):

1. Gán nhãn lại bằng prompt/guideline v1 (thử 10 câu, rồi chia phần còn lại theo hạn mức ngày của Groq).
2. Người duyệt nhãn trên `/gold` (6.7), rồi chạy `eval-mining` (6.9).
3. Dựa trên số liệu: mở rộng danh sách động từ báo cáo hoặc mẫu không có *that* (3.4), chốt danh sách từ đánh dấu (3.3), tinh chỉnh bộ lọc nhiễu (3.1b).
4. `move_classifier` (3.2), `dedup_matcher` (3.7), độ tin cậy (3.8).
5. Import: `max_articles` (1.7), hủy job (1.10), metadata journal/genre (1.5), quyết định license với SLR (1.2).
6. PDF parser (2.2c) nếu đối tác trả PDF.
7. AI hỗ trợ duyệt candidate (4.6) sau khi các stage luật có số liệu.
