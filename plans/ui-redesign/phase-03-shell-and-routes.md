# Phase 03: Shell và route

Mục tiêu: shell "Open plane" (sheet app, redraw), có nhóm điều hướng, phone gập gọn; landing nằm ngoài shell.

## Đọc trước khi làm

- `.agents/skills/design-taste-frontend/references/app-screens.md`: §3 (The shell, gồm §3.2 Sidebar), §4 (Canvas and page title), §12 (The phone)
- `taste/app-sheet.md` của plan này: §4 Shell — Open plane
- `.agents/skills/shadcn/rules/composition.md` (Sheet cần Title, item phải nằm trong Group); `npx shadcn@latest docs sidebar`, `docs command`
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
