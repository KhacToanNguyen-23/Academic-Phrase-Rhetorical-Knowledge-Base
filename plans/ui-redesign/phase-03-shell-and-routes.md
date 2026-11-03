# Phase 03: Shell và route

Mục tiêu: shell "Open plane" (sheet app, redraw), có nhóm điều hướng, phone gập gọn; landing nằm ngoài shell.

## Đọc trước khi làm

- `.agents/skills/design-taste-frontend/references/app-screens.md`: §3 (The shell, gồm §3.2 Sidebar), §4 (Canvas and page title), §12 (The phone)
- `taste/app-sheet.md` của plan này: §4 Shell — Open plane
- `.agents/skills/shadcn/rules/composition.md` (Sheet cần Title, item phải nằm trong Group); `pnpm dlx shadcn@latest docs sidebar`, `docs command`
- `.agents/plugins/skills/skills/frontend-mindset/references/responsive-performance.md` (breakpoint, touch target)

## Route

| Route | Trước | Sau |
|---|---|---|
| `/` | `OverviewPage`, đòi đăng nhập | **Landing** công khai, layout riêng không có sidebar |
| `/signin` | (LoginPage hiện thay `<Outlet>`) | Trang đăng nhập riêng, layout landing tối giản |
| `/app` | — | Trang chủ staff (phần dữ liệu của Overview cũ). Đăng nhập xong mà không có `next` thì vào đây. Logo trong shell trỏ về `/app`, logo trên landing trỏ về `/` |
| `/writer` | công khai trong shell | công khai; khách thấy shell rút gọn |
| Còn lại (`/library`, `/vocabulary`, `/extract`...) | trong shell | **giữ nguyên đường dẫn**, nằm trong `appLayout`; chưa đăng nhập thì chuyển về `/signin?next=...` |

Các màn khác giữ đường dẫn cũ để link `?batch=` từ trang Import, và link chia sẻ không gãy. Gom hết dưới `/app/*` (ví dụ `/app/library`) **không** thuộc redesign này. Nếu owner muốn làm, đó là một PR riêng: đổi path, thêm redirect từ đường dẫn cũ.

Không cho `next` chuyển hướng ra ngoài: chỉ chấp nhận đường dẫn tương đối bắt đầu bằng `/` và không bắt đầu bằng `//`.

Hai layout route trong TanStack Router: `publicLayout` (landing, signin) và `appLayout` (shell). Guard đăng nhập chuyển từ `Shell` sang `beforeLoad` của `appLayout`.

## Shell (shadcn `Sidebar`)

- Sidebar 240px trên nền trang (`--ground`), ngăn với canvas bằng một đường 1px hoặc không gì cả. Không có top bar trên desktop.
- Trên cùng: mark + "Academic Wordbank" và scope (vai trò của client). Mark mới là một khối slot vuông đặc, thay icon sách hiện tại.
- Nhóm, nhãn 12px xám sentence case:
  - **Reference**: Library, Phrasebank, Vocabulary, Journals
  - **Review**: Inbox, Gold review, Extract. Có số đếm vì đây là queue cần xử lý, ví dụ "Inbox 5"
  - **Corpus**: Import
  - **Tools**: Playground, Writer
  - Dưới cùng: Admin (chỉ admin), dòng user là `DropdownMenu` (theme light/dark, sign out)
- Nhịp nav 34px, row 32px, icon lucide 16px stroke 1.5, active là pill xám với icon và nhãn teal.
- Thu gọn thành rail icon (giữ localStorage `aprkb.sidebar.collapsed`). Rail có mark, tooltip và accessible name.
- **Phone (≤ 768px):** top bar 48px gồm tên màn, nút menu mở `Sheet` toàn màn chứa nav, tối đa một action. Giữ `inert` và trả focus như code hiện tại.
- Canvas fluid, gutter 32px; `PageHeader` cách đỉnh 32–36px. `Breadcrumb` ở màn detail.
- Bỏ footer "colophon" trong app. Câu provenance chuyển vào landing footer và trang About/Admin.
- Thêm `Command` (⌘K), tìm theo tên màn. Tìm lemma/pattern là tùy chọn, chỉ làm nếu API search sẵn có, không thêm endpoint.

## Xong khi

- `inspect.mjs --app` trên `/app`: sidebar gập trên phone, product được nêu tên, không có panel-void.
- Browser MCP: Tab qua toàn bộ nav, Esc đóng sheet, focus quay về nút menu, chuyển trang không đóng/mở lại sidebar.
- Deep link `/library?p=...` vẫn chạy; chưa đăng nhập thì quay lại đúng `next` sau khi đăng nhập.
- Đã chạy `code-review` trên PR, chú ý guard đăng nhập trong `beforeLoad` (route nào lọt guard, xử lý `next`).

## Dọn nợ từ Phase 02

- Bỏ `allow: ["edge-text"]` của `inspect.mjs` (cho chữ "Navigation" của sidebar tạm). Sidebar mới không được cần ngoại lệ.
- Xóa `src/app/Sidebar.tsx` tạm và CSS `side-*`, `masthead*` tương ứng trong `styles.css`.
- Phase này chưa có landing: `/` tạm render một placeholder công khai (tiêu đề + nút "Sign in"); Phase 04 thay bằng landing thật.

## Kết quả (2026-11-04)

Ưu tiên của owner: **thiết kế cho web desktop**, không cần tối ưu thiết bị khác. Thanh top 48px và `Sheet` cho điện thoại vẫn có (shadcn Sidebar cho sẵn) nhưng không phải gate: không đo inspect ở 390px và không kiểm Browser MCP trên cửa sổ hẹp ở các phase sau, trừ khi owner đổi ý.

Khác với spec ban đầu:

- Các route con nằm dưới layout có id nên `getRouteApi` phải dùng id đầy đủ, ví dụ `getRouteApi("/shell/guarded/library")` (`/shell/guarded/vocabulary` và `/shell/guarded/vocabulary/$lemmaId` ở hai file vocabulary). Đường dẫn URL không đổi.
- Guard chỉ nằm ở `beforeLoad` của `guarded` (và `signin` tự chuyển người đã đăng nhập). Không dùng `<Navigate>` trong component: nó gây vòng lặp vô hạn trên bản production. `App` gọi `router.invalidate()` mỗi khi phiên đăng nhập đổi.
- Số đếm chỉ có ở Inbox (đếm submission đang pending từ API có sẵn). Gold và Extract chưa có endpoint đếm rẻ, nên chưa hiện số.
- `/app` là `OverviewPage` bỏ phần hero (hero chuyển về landing ở Phase 04). Làm lại màn này ở Phase 05.
- `/` là placeholder công khai (`features/landing/PublicHome.tsx`, có `TODO(owner)`), Phase 04 thay thế.
- `CommandDialog` của shadcn bản này không bọc `<Command>`; `CommandMenu` tự bọc, nếu không `cmdk` ném lỗi `subscribe` khi mở.
- Sidebar cần `TooltipProvider` bao ngoài (đặt trong `AppShell`).
- `styles.css` có một khối tạm để link trong `[data-slot="sidebar"]` không nhận style `a` cũ; xóa cùng `styles.css` ở Phase 06.

Kiểm chứng: typecheck, lint, build pass; `dist/` không có `dev/ui`, `demo-session`; `lint.mjs --app` 0 FAIL trên các file mới (FAIL còn lại nằm trong `styles.css` cũ). Inspect `--app` trên `/app`, `/library`, `/vocabulary`, `/writer`: các lỗi của shell (`edge-text`, `panel-void` của sidebar) đã hết, không cần `allow`; FAIL còn lại là nội dung trang cũ (chữ 10px, nhãn viết hoa), thuộc Phase 05.
