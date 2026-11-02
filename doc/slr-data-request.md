# Đề xuất bổ sung dữ liệu cho SLR Repository API

**Từ:** nhóm AP-RKB (Academic Phrase & Rhetorical Knowledge Base)
**Ngày:** 31/10/2026

## 1. Bối cảnh
AP-RKB lấy bài báo từ SLR Repository API (`/public/v1/repository/works` và các endpoint artifact) để rút ra các mẫu câu học thuật. Ví dụ: cách nêu khoảng trống nghiên cứu, cách giới thiệu phương pháp, cách diễn đạt mức độ chắc chắn của kết luận.

Mỗi mẫu câu được phân loại theo **ngành** (domain → field → subfield → topic), **tạp chí**, **loại bài** và **vị trí trong bài** (Introduction, Methods…). Vì cách viết khác nhau rõ rệt giữa các ngành và giữa các phần của bài, metadata càng đầy đủ thì mẫu câu được phân loại càng chính xác.

Khi tích hợp, chúng tôi ghi nhận hiện trạng sau:

| Hiện trạng | Ảnh hưởng tới AP-RKB |
|---|---|
| Không có thông tin license hoặc quyền sử dụng ở bất kỳ trường nào của work, kể cả `originalMetadata` | Không xác định được bài nào được phép text mining |
| `GET /taxonomy` trả rỗng ở cả 4 cấp; `taxonomyVersion` và `synchronizedAt` là `null` | Không xây được bộ lọc theo ngành |
| `classification` chỉ có `topicIds`; `domainIds`, `fieldIds`, `subfieldIds` rỗng | Không phân loại được mẫu câu theo ngành |
| Một số work có `language` và `publicationType` là `null` | Bài bị loại khi lọc theo ngôn ngữ hoặc loại bài |
| Không có danh sách giá trị hợp lệ cho `language` và `publicationType` | Phía client phải đoán giá trị. Ví dụ `article` cho ra 0 bài, còn `journal-article` thì có |
| Mỗi bài cần 3–4 request (list → detail → artifacts → download), trong khi giới hạn là 120 request/phút | Mỗi lượt import chỉ lấy được khoảng 25–30 bài |

Dưới đây là các đề xuất, xếp theo mức ưu tiên. **P0** là cần để hệ thống chạy được ở production, **P1** giúp tăng rõ chất lượng phân loại, **P2** là nên có.

## 2. P0: Quyền sử dụng (license)
Chúng tôi chỉ được mining những bài có quyền rõ ràng. Đề xuất thêm vào `GET /works/{workId}`:

```jsonc
"rights": {
  "license": "cc-by",                    // mã chuẩn hóa (SPDX/CC), null nếu không rõ
  "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
  "licenseSource": "CROSSREF",           // nguồn của thông tin license
  "isOpenAccess": true,
  "oaStatus": "gold",                    // gold | green | hybrid | bronze | closed
  "fullTextVersion": "publishedVersion", // submittedVersion | acceptedVersion | publishedVersion
  "textMiningAllowed": true,             // nếu SLR có thỏa thuận hoặc điều khoản riêng
  "displayAllowed": false                // được phép hiển thị trích đoạn câu gốc hay không
}
```

Nếu không thể cung cấp theo từng bài, xin một **văn bản xác nhận ở cấp kho**: phạm vi bài nào được phép text mining, có được lưu toàn văn không, và có được hiển thị trích đoạn ngắn không.

Đề xuất thêm bộ lọc `GET /works?license=cc-by` và `?textMiningAllowed=true`.

## 3. P0: Phân loại ngành (taxonomy)
- **Đồng bộ dữ liệu cho `GET /taxonomy`** ở cả 4 cấp, kèm `taxonomyVersion` và `synchronizedAt`.
- **Điền đủ phân cấp cho mỗi work**: từ `topicIds` suy ra `subfieldIds`, `fieldIds`, `domainIds` (theo cây OpenAlex).
- **Điểm liên quan của từng topic**, để biết topic nào là chính:
  ```jsonc
  "classification": {
    "primaryTopicId": "T10917",
    "topics": [
      { "id": "T10917", "score": 0.98, "subfieldId": "S1702", "fieldId": "F17", "domainId": "D3" }
    ],
    "taxonomyVersion": "2025-01"
  }
  ```
- Bộ lọc `fieldId` / `subfieldId` / `domainId` trả đúng kết quả sau khi dữ liệu đã được điền.

## 4. P1: Thông tin tạp chí và loại bài
| Field | Mô tả | Lý do cần |
|---|---|---|
| `venue.id` | ID nguồn ổn định (ví dụ OpenAlex Source ID) | Gom bài theo tạp chí mà không phụ thuộc cách viết tên |
| `venue.issnL`, `venue.issnPrint`, `venue.issnElectronic` | Các loại ISSN | Khớp tạp chí chính xác |
| `venue.type` | journal / conference / repository / book-series | Văn phong khác nhau theo loại nơi công bố |
| `venue.subjectCategories` | Danh mục chủ đề của tạp chí (ASJC, Web of Science…) kèm hệ phân loại | Phân loại ngành ở cấp tạp chí, dùng khi bài thiếu topic |
| `venue.publisher`, `venue.country` | Nhà xuất bản, quốc gia | Phân tích văn phong theo nhà xuất bản |
| `publicationType` | Luôn có giá trị, theo danh sách cố định (ví dụ theo Crossref type) | Lọc theo loại bài |
| `articleGenre` | research-article / review / systematic-review / meta-analysis / short-communication / case-study / conference-paper / editorial / letter | Cấu trúc tu từ của bài review khác hẳn bài nghiên cứu gốc |
| `language` | Luôn có giá trị, mã ISO 639-1, kèm độ tin cậy nếu là kết quả tự nhận diện | Hiện chúng tôi chỉ mining bài tiếng Anh |
| `keywords` | Tách thành `authorKeywords` và `indexedTerms` (ví dụ MeSH) | Bổ sung ngữ cảnh chủ đề |
| `publicationDate` | Ngày đầy đủ, chuẩn hóa | Theo dõi văn phong thay đổi theo thời gian |

## 5. P1: Cấu trúc nội dung (quan trọng nhất cho việc phân loại theo vị trí trong bài)
Artifact `STRUCTURED_SECTIONS` hiện đã có `heading`, `part`, `order` và `paragraphs`. Đề xuất bổ sung:

| Bổ sung | Mô tả | Lý do cần |
|---|---|---|
| `sectionType` chuẩn hóa | abstract / introduction / literature-review / methods / results / discussion / conclusion / limitations / acknowledgements / references / appendix / other, kèm độ tin cậy | Cùng một phần nhưng tiêu đề đặt rất khác nhau, ví dụ "Materials and Methods", "Experimental Setup", "Study Design" |
| `parentSectionId`, `level` | Quan hệ cha–con giữa các section | Biết đoạn văn nằm trong phần nào ở cấp trên |
| Tách câu kèm offset | `sentences: [{sentenceId, text, start, end}]` trong mỗi paragraph | Giữ tham chiếu chính xác tới câu gốc |
| Vị trí trích dẫn trong câu | `citations: [{start, end, referenceIds}]` | Các mẫu câu như "previous studies have shown…" phụ thuộc vào vị trí trích dẫn |
| Tách riêng caption của bảng và hình, footnote | Không trộn vào đoạn văn | Tránh lẫn câu không thuộc thân bài |
| Loại bỏ header, footer, số trang | Làm sạch toàn văn | Tránh câu bị cắt đôi hoặc lẫn rác |
| Abstract có cấu trúc | `abstractSections: [{label: "background" \| "objective" \| "methods" \| "results" \| "conclusions", text}]` | Abstract có cấu trúc chứa sẵn các phần tu từ |
| Thông tin trích xuất | Công cụ và phiên bản (ví dụ GROBID 0.8.x), điểm chất lượng trích xuất, số trang | Lọc bỏ bài trích xuất kém |

## 6. P2: Thông tin tác giả (tùy chọn)
- `authors[].orcid`, `authors[].affiliations[].country`, `authorCount`.
- Dùng cho phân tích tổng hợp văn phong theo khu vực. Không cần tên hay email cá nhân, nếu chính sách của SLR không cho phép.

## 7. P1: Cải tiến API
1. **Lấy chi tiết nhiều bài trong một request**: `GET /works?include=metadata,classification,rights,artifacts` hoặc `POST /works/batch {workIds: [...]}`. Hiện mỗi bài tốn 3–4 request.
2. **Đồng bộ dần**: bộ lọc `updatedSince` và sắp xếp theo `updatedAt`, để chỉ lấy bài mới hoặc bài đã thay đổi.
3. **Facet và danh sách giá trị hợp lệ**: ví dụ `GET /works/facets?fields=language,publicationType,articleGenre,fieldId` trả các giá trị kèm số lượng bài, để giao diện hiển thị dropdown đúng dữ liệu đang có.
4. **Tài liệu ngữ nghĩa bộ lọc**: các tham số được kết hợp theo AND hay OR, và so khớp chính xác hay chuỗi con.
5. **Cursor không hợp lệ trả `400`** thay vì `500`, như đã ghi trong tài liệu hiện tại.
6. **Nâng giới hạn request**, hoặc có hạn mức riêng cho client chạy batch, nếu chưa có endpoint lấy nhiều bài một lần.
7. **Endpoint `/changes` hoặc webhook** (nếu có thể) để biết bài mới, bài bị gỡ, hoặc license thay đổi.

## 8. Tóm tắt theo mức ưu tiên
| Mức | Hạng mục |
|---|---|
| **P0** | License hoặc quyền sử dụng (theo từng bài hoặc cấp kho); đồng bộ taxonomy; điền đủ domain/field/subfield cho mỗi work |
| **P1** | `sectionType` chuẩn hóa và các bổ sung cho cấu trúc nội dung; `articleGenre`; `language` và `publicationType` luôn có giá trị; thông tin tạp chí; lấy chi tiết nhiều bài một lần; facet |
| **P2** | Thông tin tác giả; `updatedSince`; webhook; nâng giới hạn request |

Chúng tôi sẵn sàng trao đổi thêm về định dạng dữ liệu và thử nghiệm sớm trên môi trường staging của SLR.
