# UI Redesign — Before Audit

Ngày: 2026-11-03
Phase: 00 — Baseline & tooling
Nhánh: `feat/ui-redesign`

## Phạm vi và nguyên tắc

- Audit chỉ bao phủ `apps/web` và các route được nêu trong Phase 00.
- Không đọc hoặc dùng `taste/landing-sheet.md` để quyết định font hay màu.
- Token chuẩn vẫn là Token/Type trong `plans/ui-redesign/plan.md`: Switzer, Newsreader, nền giấy/ink và teal SLRS `#176b8f`.
- Không chạy `draw.mjs --redraw`.
- Sau khi chủ repo yêu cầu không chạy Playwright, không chạy thêm Playwright. Browser MCP được dùng để snapshot route local.

## Môi trường và baseline

Các lệnh tương đương Makefile đã chạy thành công:

- PostgreSQL: `docker compose up -d --wait postgres` — container healthy.
- Backend dependencies: `uv sync --directory apps/backend`.
- Migration: `uv run --directory apps/backend alembic -c alembic.ini upgrade head`.
- Seed: `uv run --directory apps/backend python -m aprkb.seeds.load`.
- Web build: `npm --prefix apps/web run build` — pass.
- Preview: `http://127.0.0.1:4173/` — reachable.
- Dev server: `http://127.0.0.1:5173/` — reachable.

`make` không có trong môi trường Windows hiện tại, nên các lệnh backend/frontend được chạy bằng lệnh tương đương trực tiếp. Backend hiện đã có process chạy ở port 8000; không khởi động thêm process trùng port.

## Route snapshot bằng Browser MCP

Đã kết nối Browser MCP, mở `http://127.0.0.1:5173/`, dùng Quick demo và snapshot các route:

| Route | Trạng thái snapshot | Ghi nhận |
|---|---|---|
| `/` | Render được | Landing overview; h1 “The right phrasing for every claim.”; có các KPI và CTA chính. |
| `/phrasebank` | Render được | Có 404 console error; màn hình vẫn có search/filter và danh sách sections/functions. |
| `/vocabulary` | Render được | H1 Academic Vocabulary; tabs Lemmas/Families và nút import. URL chuẩn hoá về `?offset=0`. |
| `/journals` | Render được | H1 Journal Profiles, navigation Journals và Overview. |
| `/inbox` | Render được | Main rỗng ở depth snapshot hiện tại; cần dữ liệu review để đánh giá trạng thái empty/list. |
| `/gold` | Render được | Có 403 console error; vẫn render bộ lọc Status/Split/Section và Review item. |
| `/extract` | Render được | Có 403 console error; batch list rỗng và nút extraction disabled. |
| `/import` | Render được | Form profile import, API key, domain/field/topic và source ordering controls. |
| `/admin` | Render được | Main rỗng ở depth snapshot hiện tại; cần kiểm tra sâu với dữ liệu request/client. |
| `/playground` | Render được | Các context controls và ba trạng thái Recommend/Render/Validate idle. |
| `/writer` | Render được | Public writer; form context, recommended patterns table và composer section. |

Authentication hiện được tập trung trong `apps/web/src/app/router.tsx`: `/writer` public; các route còn lại render `LoginPage` khi chưa có curator/admin session. Sau Quick demo, Browser MCP snapshot xác nhận session `Local Demo Curator · curator` và các route staff mở được.

## Taste-skill lint baseline

Lệnh:

```text
node .agents/skills/design-taste-frontend/scripts/lint.mjs --app apps/web/src
```

Kết quả baseline: **15 FAIL, 48 WARN**.

FAIL chính:

- `gradient`: 2 lần trong `apps/web/src/app/styles.css` — dòng 423 và 676.
- `emoji`: 13 lần trong UI phrase extraction, chủ yếu `ExtractPage.tsx` và `PhraseCard.tsx`.

WARN chính:

- `mono`: 6 lần trong `styles.css`.
- `shadow`: 33 lần.
- `transition-all`: 3 lần.
- `eyebrow`: 4 lần.
- `numbering`: 1 lần trong mock integration.
- `em-dash`: 40 lần trên toàn bộ source scan.

Đây là baseline của app hiện tại, chưa phải mục tiêu sửa trong Phase 00. Các FAIL/WARN cần được xử lý hoặc biện minh ở những phase UI tương ứng; không được âm thầm xoá vì chỉ muốn làm lint xanh.

## Inspector status

Lần chạy trong sandbox trước đó dừng ở `CDP timeout: Page.enable` với Chrome và Edge. Theo hướng dẫn của phase, `inspect.mjs` sau đó được chạy ngoài sandbox để Chrome mở được CDP debug port.

```text
node .agents/skills/design-taste-frontend/scripts/inspect.mjs --app http://127.0.0.1:4174/<route> --out .taste-skill/before/<route> --widths 1440,768,390
```

Mục 2b đã được triển khai:

- `apps/web/.env.inspect` chứa `VITE_INSPECT_AUTOLOGIN=1` và có exception trong `.gitignore` để được commit.
- `AuthProvider` chỉ tự gọi demo session khi `MODE === "inspect"` và cờ inspect bật; trong lúc request giữ `loading`.
- Có scripts `build:inspect` và `preview:inspect`; preview inspect chạy ở port 4174.
- Build production không chứa chuỗi `demo-session`; build inspect có nhánh auto-login.

Browser MCP đã xác minh `http://127.0.0.1:4174/library` tự đăng nhập thành `Local Demo Curator · curator` và hiển thị nội dung staff.

Inspector đã chạy cho 12 route (`/`, `/library`, `/phrasebank`, `/vocabulary`, `/journals`, `/inbox`, `/gold`, `/extract`, `/import`, `/admin`, `/playground`, `/writer`). Mỗi route có `report.json` và 6 ảnh JPG tương ứng fold/page ở 1440/768/390 trong `.taste-skill/before/<route>/`.

| Route | FAIL | WARN | Ghi chú |
|---|---:|---:|---|
| `/` | 2 | 5 | Baseline overview hiện tại vẫn là app screen có hero lớn. |
| `/library` | 2 | 4 | Có dữ liệu library và detail pane. |
| `/phrasebank` | 1 | 4 | Baseline có edge-text/nav và panel void. |
| `/vocabulary` | 3 | 3 | Có tiny text và thiếu tabular numerals. |
| `/journals` | 1 | 5 | Có ragged row/panel void. |
| `/inbox` | 1 | 4 | Có dữ liệu incoming và contrast thấp ở một số trạng thái. |
| `/gold` | 2 | 5 | Curator xem được màn review baseline. |
| `/extract` | 1 | 3 | Empty batch state được đo. |
| `/import` | 2 | 3 | Form import dài tạo ragged rows. |
| `/admin` | 2 | 4 | Demo client là curator nên hiển thị “Admin role required”; đây là trạng thái quyền thật của baseline. |
| `/playground` | 2 | 5 | Ba panel idle được đo. |
| `/writer` | 2 | 4 | Numeric alignment/tabular và micro-label là cảnh báo baseline. |

Các FAIL/WARN này là bằng chứng before, chưa phải phạm vi sửa của Phase 00. Route folder baseline được giữ trong `.taste-skill/` và thư mục này đã được thêm vào `.gitignore`.

## E2E baseline

Đã sửa `apps/web/e2e/phrasebank.spec.ts` để thư mục screenshot không còn hard-code vào profile người dùng khác; mặc định dùng `test-results/screens`, có thể override bằng `E2E_SCREENSHOT_DIR`.

Sau khi chủ repo yêu cầu không chạy Playwright, không chạy thêm Playwright. Trước yêu cầu đó, lần chạy thử duy nhất cho thấy 6/8 test pass và 2 test fail ở baseline hiện tại:

- Phrasebank assertion đang chờ màu cũ `rgb(100, 115, 129)`, app trả `rgb(93, 109, 120)`.
- Writer assertion không tìm thấy mô tả `Name the specific topic discussed in your evidence.`.

Hai lỗi này không được sửa trong Phase 00 vì sẽ mở rộng phạm vi từ baseline/tooling sang thay đổi hành vi hoặc hợp đồng test của app.

## Frontend review findings

### P1 — cần theo dõi ở các phase UI

- Route `/` hiện vẫn nằm trong Shell/auth flow và chỉ hiển thị landing overview sau khi có session; plan mục tiêu yêu cầu `/` public landing và `/app` staff home. Đây là thay đổi route/auth của Phase 03–04, chưa sửa ở Phase 00.
- App có nhiều lớp style legacy trong `styles.css`; lint cho thấy gradient, shadow và emoji UI còn tồn tại. Cần migration có kiểm soát, tránh thay toàn bộ token một lần.
- `/gold` và `/extract` có 403 API trong demo session; cần phân biệt quyền API, empty state và lỗi tải dữ liệu trong Phase 05.

### P2 — cần kiểm tra trong component phases

- `/inbox` và `/admin` snapshot không cho thấy nội dung ở depth hiện tại; cần audit empty/loading/error states đầy đủ.
- `Sidebar` có responsive collapsed/mobile behavior và focus restoration; cần kiểm tra bằng keyboard và viewport mobile ở Phase 03.
- `styles.css` đang chứa nhiều shadow, monospace và `transition: all`; cần thay theo component/token, không sửa cơ học toàn file.

### P3 — polish

- Các chuỗi có encoding lỗi hiển thị trong source snapshot cần được rà lại khi chạm vào component tương ứng.
- Cần kiểm tra font glyph tiếng Việt khi nạp Switzer/Newsreader theo Token/Type trong plan; fallback phải được khai báo có chủ đích.

## Phase 00 changes

- Tạo nhánh `feat/ui-redesign` từ trạng thái hiện tại để không phá các thay đổi dirty của workspace.
- Thêm `.taste-skill/` vào `.gitignore`.
- Đổi thư mục screenshot hard-code trong `apps/web/e2e/phrasebank.spec.ts` thành biến môi trường/fallback repo-local.
- Thêm cấu hình project-scoped Browser MCP vào `.mcp.json`; Browser MCP đã được approve và snapshot local page thành công.
- Thêm build/preview inspect, `.env.inspect` auto-login và exception `dist-inspect/`/`.env.inspect` trong `.gitignore`.
- Chạy `inspect.mjs` ngoài sandbox cho mọi route; đủ `report.json` và ảnh 3 viewport cho từng route.

## Gate

Phase 00 đã hoàn tất baseline/tooling theo phạm vi của phase. E2E không chạy lại theo quyết định owner; baseline 2/8 test fail được giữ trong report, không phải blocker của phase. Không chuyển sang Phase 01 trong turn này; cần dừng để báo cáo sau `code-review`.
