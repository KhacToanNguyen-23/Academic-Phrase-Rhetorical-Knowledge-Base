# Phase 07: Polish (làm các màn đầy đặn hơn)

Phase 05 làm đúng cấu trúc và pattern, nhưng nhiều màn còn phẳng: bảng cộng thẻ trắng trên nền xám, ít thông tin tóm tắt, khoảng trống không có việc gì, empty state chưa chỉ bước tiếp. Phase này nâng chất lượng nội dung và mật độ thông tin của từng màn. Không thêm tính năng, endpoint hay trang mới.

## Phạm vi và ràng buộc (đã chốt)

- **Chỉ desktop** (1440px, tối thiểu 1024px). Không mobile, không tablet.
- **Không thêm API, không đổi backend, không đổi route.** Mọi số liệu hiển thị phải tính được từ dữ liệu mà màn đang có hoặc từ API đã tồn tại. Không bịa số liệu, tên hay xu hướng. Nếu một ý tưởng cần dữ liệu chưa có, ghi vào báo cáo thay vì làm giả.
- **Giữ ngôn ngữ thiết kế:** `achromatic-ledger`, teal tiết chế (tối đa một nút primary mỗi màn, active nav, slot), không gradient, không bóng khi nghỉ, không eyebrow, không chữ hoa có tracking, không hairline trang trí, không thẻ icon lặp lại. Hình dữ liệu dùng tông trung tính, chỉ một phần được nhấn.
- Không thêm thư viện. Vẽ biểu đồ bằng div và CSS hoặc SVG tối giản (không thư viện chart), vì số lượng chart ít.
- Dòng ≤ 120 ký tự, có dấu chấm phẩy, pnpm, không Playwright.

## Bước 0: Chấm điểm hiện trạng (làm trước, ra danh sách)

Với mỗi màn trong bảng dưới, mở ảnh `inspect --app --widths 1440` và chấm theo `.agents/skills/design-taste-frontend/references/critique.md` (14 lượt, có điểm). Ghi vào `plans/reports/` một bảng: màn, điểm, 3 vấn đề lớn nhất. Dùng bảng này để xếp thứ tự; màn điểm thấp làm trước. Owner có thể gạch bớt màn.

## Tiêu chí hoàn thành chung (mỗi màn)

1. Nhìn trong 5 giây trả lời được: đây là gì, cần làm gì tiếp.
2. Không có khối trống liền mạch cao hơn 300px trong vùng nội dung (inspector không còn `hero-void`, `panel-void` do thiết kế sai; WARN còn lại có một câu giải thích).
3. Mỗi danh sách có tiêu đề cột, số đếm, trạng thái chọn và hover rõ; cột chính nổi hơn cột phụ; cột số căn phải, `tabular-nums`.
4. Mỗi empty/loading/error state có nội dung riêng cho màn đó và một bước tiếp theo (nút hoặc câu chỉ đường), không dùng câu chung.
5. Thao tác ghi (approve, reject, tạo, import) có phản hồi rõ: toast (`sonner`) hoặc trạng thái tại chỗ, và tắt nút khi đang chạy.
6. Điểm critique của màn tăng so với bước 0 và không có mục nào dưới 6/10 ở lượt "hierarchy", "density" và "states".

## Việc theo màn (giả thuyết ban đầu, xác nhận ở bước 0)

| Màn | Vấn đề thấy được | Hướng nâng |
|---|---|---|
| `/app` | 4 con số rời rạc, phần dưới trống, danh sách cắt chữ | Dải số liệu có ngữ cảnh (so với tổng, link đúng hàng đợi). Khối "Cần xử lý": mục đầu của Inbox, Gold, Extract kèm nút vào thẳng. Thành phần bank theo trạng thái và theo section (thanh ngang trung tính). Hoạt động gần đây có giờ tương đối. Lấp khoảng trống bằng nội dung có việc để làm |
| Vocabulary | Chỉ có bộ lọc rồi bảng | Dải tóm tắt (tổng lemma, family, core, số theo band) tính từ dữ liệu có sẵn; phân bố rank/band bằng một biểu đồ nhỏ; hàng bảng hiện thêm một dòng phụ (family, ví dụ) nếu API có |
| Vocabulary detail | Ít thông tin | Bố cục từ điển: headword lớn, các dạng từ nhóm theo loại từ, rank và band thành dải số, link về đúng bộ lọc cũ |
| Library | Danh sách và chi tiết cùng một kiểu | Dải đếm theo trạng thái ở đầu; hàng danh sách hiện section, intent, độ mạnh; chi tiết nhóm theo "Dùng thế nào / Nguồn gốc / Biến thể" với tiêu đề rõ |
| Phrasebank | Phần lớn là trạng thái tắt | Khi reference library tắt, trang dẫn người dùng thẳng sang AP-RKB patterns theo section (không để thẻ "unavailable" chiếm chỗ); khi bật, nhóm theo section kèm số đếm |
| Journals | Overview trống ("Select a journal") | Mặc định hiện so sánh các journal cạnh nhau (số guideline đã xác minh, số quan sát corpus), chọn một journal mới vào chi tiết |
| Inbox, Gold, Extract | Ổn về cấu trúc, thiếu nhịp làm việc | Tiến độ hàng đợi ("3 of 12 reviewed" nếu tính được), phím tắt hiển thị bằng `<kbd>`, mục kế tiếp tự chọn sau khi duyệt, câu gốc và frame đặt cạnh nhau |
| Import, Admin | Settings chung chung | Trạng thái job thành chuỗi bước đọc được, log có lọc theo client và mã trạng thái, key mới có hướng dẫn lưu |
| Playground, Writer | Form dài, kết quả ở dưới | Tóm tắt ngữ cảnh đang dùng, kết quả đặt gần nơi nhập, JSON có nút copy |
| Sign-in | Quá trống | Một dòng nói rõ mục đích và nơi lấy key; không thêm trang trí |

## Đợt làm (mỗi đợt một PR vào `feat/ui-redesign`)

1. **A, các màn nhìn thấy đầu tiên:** `/app`, Library, Vocabulary, Vocabulary detail, Journals.
2. **B, các màn làm việc:** Inbox, Gold, Extract, Writer, Playground.
3. **C, còn lại:** Phrasebank, Import, Admin, Sign-in.

Mỗi đợt chạy `code-review` và xử lý P0/P1, rồi báo cáo kèm điểm critique trước và sau.

## Gate (mỗi màn)

- `pnpm typecheck && pnpm lint && pnpm build`; `dist/` không có `dev/ui`, `demo-session`.
- `lint.mjs --app` 0 FAIL; `inspect.mjs --app --widths 1440` 0 FAIL, WARN có giải thích.
- Script teal: tối đa một nút primary mỗi màn, không nền teal ngoài nút, toggle, radio.
- Mở và xem ảnh, ghi điểm critique mới. Tối đa 3 vòng mỗi màn.
- Kiểm bằng Browser MCP hoặc script CDP: mọi thao tác ghi và mọi state mới.

## Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Thêm số liệu làm màn nhiều chữ hơn mà không hữu ích | Mỗi con số phải dẫn tới một hành động hoặc một quyết định; không có thì bỏ |
| Số liệu giả để màn trông đầy | Cấm. Dữ liệu mock chỉ được dùng nếu màn đó vốn đã dùng mock, và ghi rõ trong báo cáo |
| Biểu đồ phá quy tắc màu | Một hue trung tính, nhấn một phần bằng đậm hơn; không teal, không cầu vồng |
| Gold, Extract, Admin cần khóa admin để thấy dữ liệu thật | Làm việc với admin key hoặc phiên admin cho môi trường dev; nếu không có thì ghi rõ phần chưa kiểm |
