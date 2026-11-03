# ADR-0006: Nhập bài báo từ SLR Repository API theo bộ lọc do curator cấu hình

- Trạng thái: Accepted
- Ngày: 2026-10-31
- Bổ sung cho: [ADR-0005](0005-external-article-source.md)

## Bối cảnh
Nguồn bài báo được chọn là SLR Repository API (`https://slr-api.hyperdatalab.org`, spec tại `/repository-api-docs.json`). API chỉ tìm trong kho bài SLR đã lưu, không tìm trên Internet. Xác thực bằng header `X-API-Key`; key do admin SLR cấp kèm scope và danh sách project được phép. Giới hạn 120 request/phút cho mỗi client và IP.

Các endpoint dùng cho luồng lấy bài (tất cả là GET dưới `/api/public/v1/repository`):

| Endpoint | Dùng để |
|---|---|
| `/works` | Liệt kê bài theo bộ lọc, phân trang bằng `cursor`/`nextCursor`, `limit` ≤ 100. Chỉ trả `workId`, `doi`, `title` |
| `/works/{workId}` | Metadata, phân loại OpenAlex, `availability`, `metadataSources[].originalMetadata` |
| `/works/{workId}/artifacts?kind=` | Danh sách artifact READY |
| `/works/{workId}/artifacts/{artifactId}/download` | Tải nội dung; cần scope `repository:read` và `artifacts:download` |
| `/taxonomy`, `/taxonomy/{level}/{taxonId}/children` | Cây domain → field → subfield → topic cho giao diện chọn ngành |

Không dùng `POST /works/import` (đẩy bài lên SLR, cần `repository:write`), các endpoint `analysis-*` và `*-schemas`.

Spec SLR **không có trường license**. Chỉ `originalMetadata` (dạng tự do) có thể chứa license của nguồn gốc.

## Quyết định
- Thêm adapter `SlrRepositorySource` (`ARTICLE_SOURCE=slr`) cài đặt `ArticleSource`. `list_articles` gọi `/works` rồi `/works/{workId}`; `fetch_content` chỉ chạy sau khi kiểm tra license, tải artifact theo thứ tự ưu tiên trong profile. Các loại được phép là `FULLTEXT_MARKDOWN`, `FETCHER_FULLTEXT_MARKDOWN` và `SOURCE_PDF`; mặc định theo đúng thứ tự đó.
- Bộ lọc do curator cấu hình trên giao diện web và lưu thành **`ImportProfile`** trong PostgreSQL. Các field lọc được phép là các tham số của `/works`: `domainId`, `fieldId`, `subfieldId`, `topicId`, `q`, `doi`, `openAlexId`, `journal`, `journalIssn`, `language`, `publicationType`, `yearFrom`, `yearTo`, `hasPdf`, `hasFullText`, `hasAnalysis`. Field lạ bị từ chối khi validate.
- Khi curator bấm "Lấy bài báo", API tạo job `import_articles` và **chụp bộ lọc của profile vào payload job**. Sửa profile sau đó không làm thay đổi job đang chạy hay đã chạy. Mọi thao tác tạo, sửa profile và tạo job đều ghi `AuditEvent`.
- **License fail closed.** License đọc từ `metadataSources[].originalMetadata`, rồi map sang mã trong bảng `licenses` qua bảng ánh xạ trong `policies/licenses.yaml`. Thiếu license, chuỗi không có trong bảng ánh xạ, hoặc `allows_mining = false` thì bỏ qua bài, không tải nội dung.
- Danh sách license và quyền `allows_mining`/`allows_display` chuyển từ `seeds/load.py` sang `policies/licenses.yaml`. CC0, CC-BY, CC-BY-SA cho mining và display. Các biến thể NC và ND tạm **chặn** với `TODO(owner)` cho đến khi chủ dự án quyết định.
- Không dùng OpenAlex API. ID taxonomy OpenAlex chỉ là giá trị bộ lọc do SLR trả về.
- Adapter xử lý `429` theo `Retry-After`. API key SLR lấy từ biến môi trường `SLR_API_KEY`, không ghi vào log, audit hay payload job.
- Giao diện là một màn hình trong `apps/web` chạy như web bình thường, gọi API thật qua client sinh từ OpenAPI (ADR-0004): chọn hoặc sửa profile, bấm lấy bài, xem tiến độ job qua `GET /v1/admin/jobs/{id}`.

## Hệ quả
- Nếu kho SLR không có license trong `originalMetadata`, mọi bài sẽ bị bỏ qua. Khi đó cần SLR bổ sung license hoặc chủ dự án xác nhận quyền mining cho cả nguồn, và ghi quyết định đó vào `policies/licenses.yaml`.
- Parser PDF vẫn là stub (ADR-0005), nên bài tải về dạng PDF được lưu nhưng job ingest báo lỗi cho đến khi có parser. Muốn mining được ngay thì để markdown đứng trước PDF trong `artifact_kinds`.
- Test dùng HTTP giả lập, không gọi SLR thật trong CI.
- Cần xác nhận với SLR rằng điều khoản sử dụng cho phép text mining và lưu nội dung.
- Spec không xác nhận các giá trị hợp lệ của `language`/`publicationType` và cách các bộ lọc được kết hợp; cần kiểm tra bằng key thật.

## Ngoại lệ cho môi trường phát triển (2026-10-31)
Kiểm tra SLR thật cho thấy không có license ở bất kỳ trường nào, kể cả `originalMetadata` từ OPENALEX, CROSSREF, GROBID và PDF. Vì vậy, nếu giữ fail closed thì mọi bài đều bị bỏ qua. Trong giai đoạn phát triển, chủ dự án chấp nhận bỏ qua yêu cầu license, với các giới hạn sau:
- `SLR_DEV_FALLBACK_LICENSE` (mặc định trống) gán license `DEV-UNVERIFIED` cho bài SLR thiếu license hoặc có chuỗi license không nhận ra. Bài có license đã biết nhưng `allows_mining = false` (ví dụ NC/ND) vẫn bị chặn.
- App không khởi động nếu đặt giá trị này khi `APP_ENV` khác `local`/`test`. Mã license phải có trong `licenses.yaml`.
- Phần kiểm tra license trong importer, worker, review và `LicenseGate` giữ nguyên.
- `TODO(owner, BR-10)`: trước khi lên production, xóa các bài có license `DEV-UNVERIFIED` cùng dữ liệu sinh ra từ chúng, bỏ mã này khỏi `licenses.yaml`, và chốt nguồn quyền mining thật (SLR bổ sung license hoặc có thỏa thuận cấp nguồn).

## Quyết định khi cài đặt
- `ArticleSource.list_articles` nhận `ImportOptions` bất biến gồm bộ lọc và thứ tự `artifact_kinds`; `SourceArticleRef.content_locator` giữ ID artifact để tải sau khi qua các kiểm tra quyền.
- Importer kiểm tra license → định dạng → trùng lặp → tải nội dung. Sai kích thước, MIME hoặc SHA-256 raise `InvalidContentError` và chỉ bỏ qua bài đó.
- `jobs.result` lưu `ImportSummary`; job trang tiếp theo nhận cùng `profile_id`, bộ lọc và thứ tự artifact đã chụp từ job trước.
- Download kiểm tra `sizeBytes`, giới hạn byte cấu hình và checksum khi `checksumAlgorithm` là `SHA-256`.
- Adapter đọc envelope thành công `{isSuccess, data, errors}`; envelope lỗi dùng `{success:false,error:{code,message}}` và không được chuyển tiếp chi tiết nhạy cảm lên API.
- Chưa xác nhận từ dữ liệu thật vị trí license trong `originalMetadata`, ngữ nghĩa AND của bộ lọc, và giá trị hợp lệ của `language`/`publicationType` (`TODO(owner, PRD-04)`).
