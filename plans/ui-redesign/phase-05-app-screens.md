# Phase 05: App screens

Làm theo run app-screens của taste skill (`references/app-screens.md` §2). Style là [taste/app-sheet.md](taste/app-sheet.md) (`achromatic-ledger`, shell Open plane).

## Đọc trước khi làm

- `.agents/skills/design-taste-frontend/references/app-screens.md`: **toàn bộ** (yêu cầu của chính file đó)
- `taste/app-sheet.md` của plan này: §5 Screens (pattern Inbox triage, Settings two columns)
- `.agents/skills/shadcn/rules/forms.md`, `composition.md`, `styling.md`
- `.agents/plugins/skills/skills/frontend-mindset/references/copy.md`, `production-hardening.md` (input dài, lỗi theo status code), `review-checklist.md`

## Vòng làm cho mỗi màn

Mỗi màn đi qua cùng một vòng:

1. **Inventory dữ liệu và việc** (§2.1): object, field, độ lớn thật, ai mở, việc tiếp theo. Ghi vào đầu PR.
2. **Câu hỏi của màn** (§2.2): thứ lớn nhất trên màn phải trả lời câu đó.
3. Thay markup bằng component shadcn và component miền. Giữ nguyên query, mutation, search params, route.
4. **States** (§2.6, §11): loading, empty, zero, error cho từng block; hover, selected, focus, disabled cho từng row và control.
5. Xóa phần CSS tương ứng trong `styles.css`.
6. **Gate:** `lint.mjs --app` + `inspect.mjs --app --widths 1440` trên build, 0 FAIL. Trả lời 7 câu critique ở §2.7. Tối đa 3 vòng.
7. Click qua bằng Browser MCP (chỉ desktop), ghi kết quả từng thao tác và lỗi console. Đo bằng build `inspect` (Phase 00, mục 2b), vì đây là route staff. Không chạy Playwright.

## Bảng màn

| Màn | Câu hỏi | Pattern | Điểm chính |
|---|---|---|---|
| `/app` | Hôm nay cần xử lý gì? | Workspace home | Một dải KPI chia bằng divider (Inbox chờ, gold chờ, extract chờ, pattern approved). Số là chữ, không phải tile. Danh sách gần đây có giới hạn số dòng và "View all" |
| `/vocabulary` | Từ này nằm ở đâu trong danh sách học thuật? | List + index A–Z | `ToggleGroup` lemmas/families; `Select` sort; chữ cái là thanh index; bảng có rank căn phải, `tabular-nums`; `Pagination` |
| `/vocabulary/$lemmaId` | Từ này dùng thế nào? | Detail kiểu entry từ điển | `DictionaryEntry`: headword Newsreader cỡ lớn, family, rank, ví dụ; `Breadcrumb` quay về đúng filter đã chọn |
| `/library` | Pattern nào hợp với claim này? | List + detail pane | Bộ lọc là `Select`/`Combobox` (section, intent, evidence); detail hiện `PhraseFrame`, slot, contract, variant, provenance |
| `/phrasebank`, `/phrasebank/$slug` | Trong move này có những phrase nào? | List theo nhóm | Các category là danh sách có số đếm; trang category giữ thứ tự bảng gốc (kiểm bằng Browser MCP, đối chiếu với `e2e/phrasebank.spec.ts` để biết thứ tự cần giữ) |
| `/journals`, `/journals/$id` | Journal này viết khác gì phrasebank gốc? | List + detail | Tách hẳn "Verified guidelines" và "Observed in corpus" thành hai section có heading riêng |
| `/inbox` | Submission nào cần duyệt tiếp? | **Inbox triage** (sheet) | Danh sách 384px có tabs/search/count; item đang mở; cột details 320px dạng key-value. Approve là primary teal (nút teal duy nhất của màn), Reject là secondary; `AlertDialog` chỉ cho thao tác không hoàn tác được |
| `/gold` | Nhãn AI nào cần người duyệt? | Inbox triage | Cùng khung với Inbox; frame và câu gốc đặt cạnh nhau; phím tắt có `<kbd>` |
| `/extract` | Phrase nào trích từ batch này đáng giữ? | Inbox triage + chọn batch | `ArticleCard`/`PhraseCard`/`MaskedFrame` dựng lại trên `PhraseFrame`; `Combobox` chọn batch (`?batch=`) |
| `/import` | Profile nào đang chạy, tiến độ ra sao? | **Settings two columns** (sheet) | Cột label 450px + panel `#fafafa`; `Field`/`FieldGroup`; tiến độ job bằng chữ và số, không spinner vô hạn |
| `/admin` | Client nào đang gọi API, gọi gì? | Settings + bảng log | Bảng log: thời gian căn phải, ID mono; tạo key bằng `Dialog`, key chỉ hiện một lần kèm nút copy |
| `/playground` | Engine trả gì cho ngữ cảnh này? | Builder hai cột | Form ngữ cảnh bên trái (`Field`), JSON và kết quả bên phải; JSON hiện trong `<pre>` (mono hợp lệ ở đây) |
| `/writer` | Câu tôi viết có hợp không? | Composer | Context form + composer + kết quả + validation V01–V08 bằng `Alert` theo mức độ; khách xem được |
| `/signin` | — | Một form | `Field` API key, nút đăng nhập, nút demo; lỗi hiện qua `aria-describedby` |

## Đợt

1. **Reference:** vocabulary, library, phrasebank, journals (ít mutation nhất, dễ dựng `PhraseFrame`/`DictionaryEntry`)
2. **Review:** inbox, gold, extract (dùng chung khung triage)
3. **Corpus/Admin:** import, admin (settings pattern)
4. **Tools:** playground, writer, signin, `/app`

Mỗi màn, trước khi merge: đúng **một** nút primary teal cho việc chính của màn. Không có tab, card, header hay nền nào màu teal.

Mỗi đợt một PR vào `feat/ui-redesign`. Không gom nhiều đợt vào một PR. Mỗi PR chạy `code-review` và xử lý các finding trước khi merge.

## Dữ liệu mẫu

Các màn còn dùng mock (`shared/api/mock-*.ts`) phải có tên và số tin được (không Acme, không "User 1"), tổng cộng phải khớp, ngày theo thứ tự. Liệt kê các mock này trong report để thay dần bằng dữ liệu thật.

## Danh sách chỉnh cuối phase (từ review đợt 1 và 2, 2026-11-04)

Làm một lần sau đợt 4, trước Phase 06:

- Vocabulary: hàng bộ lọc lệch nhau, bảng chữ cái tràn sang hàng hai, bỏ cột "Details" vì tên từ đã là link, canvas lệch (cách sidebar 49px, cách mép phải 149px).
- Library: hai thẻ Slots và Provenance còn khoảng trống, danh sách trái lệch chiều cao với chi tiết phải.
- Phrasebank, Journals: mình chưa xem tận mắt, cần soi lại (Journals có 4 WARN).
- Font: inspector báo Be Vietnam Pro "chưa nạp" ở các màn app dù CDP cho thấy đã tải. Xác nhận lại.
- Extract: đổi checkbox chọn batch thành Combobox (`?batch=`); thêm nút xóa bộ lọc article.
- Inbox: thêm ô tìm kiếm.
- Reject: thống nhất một kiểu xác nhận giữa Inbox, Gold, Extract (hiện Inbox và Gold có hộp xác nhận, Extract thì không; phím R ở Gold nay mở hộp xác nhận, owner cần đồng ý).
- Kiểm Gold và Extract bằng khóa admin (phiên demo là curator nên API admin trả 403, chưa thấy dữ liệu thật).
- Quy tắc nút primary: màn chỉ để đọc là "tối đa một".

### Trạng thái danh sách chỉnh (2026-11-04)

Đã làm: Vocabulary (hàng bộ lọc, bảng chữ cái một hàng, bỏ cột Details), Library (thẻ không còn kéo giãn), Inbox (ô tìm kiếm), Extract (nút "Show all articles", xác nhận khi reject một phrase, giống Inbox và Gold), Admin (bắt lỗi clipboard khi copy key).

Giữ có chủ ý: Extract vẫn chọn batch bằng checkbox, không dùng Combobox một lựa chọn, vì màn này khai thác nhiều batch cùng lúc.

Chưa làm: xác nhận phím R ở Gold (owner đồng ý), kiểm Gold, Extract và hộp tạo key bằng khóa admin thật (phiên demo là curator), soi lại Phrasebank và Journals, xác nhận font app.
