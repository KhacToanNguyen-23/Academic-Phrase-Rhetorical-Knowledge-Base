# Plan: Redesign toàn diện UI web (Refined Editorial Workspace)

Ngày: 2026-11-03
Rủi ro: trung bình đến cao. Chỉ đổi `apps/web`: thêm Tailwind v4 + shadcn/ui, thay toàn bộ CSS và markup các trang, đổi route `/` và chuyển auth guard. Backend, API contract và dữ liệu không đổi.
Trạng thái: owner đã chốt 4 quyết định ngày 2026-11-03 (xem [Quyết định của owner](#quyết-định-của-owner-2026-11-03)). Sẵn sàng làm Phase 00.

## Mục tiêu

1. Một **landing page** công khai tại `/`, làm theo run trang của taste skill (`design-taste-frontend`), có thể dùng thư viện ngoài. Trang chủ staff chuyển sang `/app`.
2. Toàn bộ **app screens** (library, phrasebank, vocabulary, journals, inbox, gold, extract, import, admin, playground, writer) làm lại theo `references/app-screens.md` của taste skill.
3. Mọi control (button, dropdown, select, dialog, tabs, table, toast...) dùng **component shadcn/ui**.
4. Ngôn ngữ thiết kế: **Refined Editorial Workspace**, tức thẩm mỹ biên tập học thuật kết hợp công cụ nghiên cứu hiện đại (xem [Hướng thiết kế](#hướng-thiết-kế-cập-nhật-2026-11-04)). Thay cho hướng "tối giản, hình học" ban đầu.
5. Kiểm tra bằng `inspect.mjs` của taste skill (đo theo house rules) và Browser MCP (thao tác thật trên trình duyệt). **Không chạy Playwright** (quyết định owner #5).

Ngoài phạm vi: không thêm endpoint, không đổi `packages/contracts`, không thêm tính năng nghiệp vụ mới. Không admin console mới, không NLP mới (theo `SCAFFOLD_PRD.md`).

## Hiện trạng (đã khảo sát)

- Vite 6 + React 18 + TanStack Router/Query/Table. **Chưa có Tailwind**; một file `src/app/styles.css` dài 1683 dòng, token đồng bộ SLRS (`--color-primary: #176b8f`, Inter, radius 6/8/12, shadow).
- `src/shared/ui/*` là primitive tự viết, *giả* shadcn (`cn` tự viết, class `ui-button-*`), không phải shadcn thật.
- Shell: masthead 64px + sidebar có icon tự vẽ, thu gọn được. 11 đích điều hướng.
- `/` hiện là `OverviewPage` (hero có eyebrow, gradient card, `hero-points` có dấu tick), đòi đăng nhập; chỉ `/writer` công khai.
- e2e: `e2e/phrasebank.spec.ts`, `e2e/writer.spec.ts`. Đường dẫn screenshot hardcode `C:/Users/khact/...`, máy khác không chạy được.
- Quản lý gói chỉ bằng **pnpm** (CI dùng `pnpm install --frozen-lockfile`). `package-lock.json` đã bị xóa; `Makefile`, `dev.ps1` dùng `pnpm --dir apps/web`.
- Browser MCP: `@browsermcp/mcp` mới cấu hình trong Codex (`~/.codex/config.toml`), **chưa có trong Claude Code**. Máy có Chrome và Edge, Node 24, đủ cho `inspect.mjs`.
- Nhánh hiện tại `feat/academic-vocabulary` còn nhiều thay đổi chưa commit ở `apps/web` (Sidebar, vocabulary, styles.css).

## Skill dùng và thứ tự ưu tiên

Các skill trong repo mâu thuẫn nhau (ví dụ `minimalist-ui` cho phép pill badge chữ hoa và hairline, taste skill cấm). Khi xung đột, lấy theo thứ tự sau.

Các skill này nằm ở `.agents/` (thư mục của Codex/Antigravity), **không nằm ở `.claude/skills/`**, nên Claude Code không tự nạp chúng. Ở mỗi phase, agent phải tự đọc các file trong mục "Đọc trước khi làm". Hai skill `frontend-mindset` và `minimalist-ui` nằm trong thư mục **plugin**, không nằm trong `.agents/skills/`.

| Ưu tiên | Skill | Đường dẫn | Dùng cho |
|---|---|---|---|
| 1 | Brief của owner + `CLAUDE.md` | `CLAUDE.md` | Phạm vi, seed tự viết, không lộ nội dung có bản quyền |
| 2 | `design-taste-frontend` (taste skill v2) | `.agents/skills/design-taste-frontend/` (`SKILL.md` cho landing, `references/app-screens.md` cho app) | Direction, token, house rules, gate `lint.mjs`/`inspect.mjs`, vòng critique |
| 3 | `shadcn` | `.agents/skills/shadcn/` (`SKILL.md`, `rules/*.md`) | Cấu trúc component, rule composition/forms/icons, CLI |
| 4 | `frontend-mindset` | `.agents/plugins/skills/skills/frontend-mindset/` (`SKILL.md`, `references/*.md`) | Đủ 8 trạng thái tương tác, a11y, copy, responsive, review checklist |
| 5 | `minimalist-ui` | `.agents/plugins/skills/skills/minimalist-ui/SKILL.md` | Chỉ lấy phần không xung đột: sự kiệm màu, `<kbd>`, một serif cho văn bản trích dẫn |
| — | `redesign-existing-projects` | `.agents/skills/redesign-existing-projects/SKILL.md` | Chỉ dùng checklist audit ở Phase 00 |
| — | `code-review` | Claude Code: skill `/code-review`; Codex: `.agents/skills/code-review/SKILL.md` | Bắt buộc trước mỗi PR |
| — | `gpt-taste`, `high-end-visual-design` | `.agents/skills/` | **Không dùng.** Floating glass pill nav, GSAP ở mọi section, cấm 1px border: trái với taste skill và app-screens |

Kiểm tra trên trình duyệt: Claude Code dùng Browser MCP (`@browsermcp/mcp`, cài ở Phase 00); Codex dùng skill trình duyệt có sẵn của nó. Cả hai chạy cùng một checklist.

Mâu thuẫn shadcn với taste: shadcn mặc định có shadow, radius 0.625rem, `ring`. Cách xử lý là **sửa token và variant một lần trong `components/ui/*`** (đó là source của mình), không override bằng `className` ở từng chỗ dùng. Rule "className cho layout, không cho style" của shadcn nhờ vậy vẫn giữ được.

## Direction đã deal (taste skill)

Chi tiết đầy đủ ở [taste/landing-sheet.md](taste/landing-sheet.md) và [taste/app-sheet.md](taste/app-sheet.md). JSON để tái lập ở `taste/*-direction.json`.

> **Cảnh báo:** mục Type (§3) và Colour (§4) của `taste/landing-sheet.md` **đã bị thay thế**. Lấy font và màu từ mục [Token](#token) và [Type](#type) của file này: Switzer + Newsreader; giấy, mực và **teal SLRS** (quyết định owner). Không dùng Big Shoulders, Public Sans, Tobacco and olive, crimson hay cam. Không chạy `draw.mjs --redraw` thêm lần nào, vì mỗi lần chạy sẽ ghi đè sheet.

### Landing: `sentence-as-layout`, seed 568972173

Deal 3 option (`page-is-the-object`, `type-only-statement`, `sentence-as-layout`). Chọn `sentence-as-layout` vì nó khớp với chính đối tượng của sản phẩm: một phrase frame là câu có **slot**, tức có một chỗ trống ở vị trí của một từ. Direction này cũng đặt "một thứ của chủ thể vào trong câu, ở chỗ một từ".

**Câu ý tưởng:** *On this page, the slot of a phrase frame becomes the media slot inside the headline.* (Thử thay đối thủ vào: một bộ từ điển khác không có frame có slot mined theo journal, nên ý tưởng này thuộc riêng sản phẩm.)

**Live thing:** một `ToggleGroup` chọn rhetorical move (Gap, Method, Finding, Limitation). Slot trong headline đổi sang một frame tự viết của move đó, kèm nhãn độ mạnh claim (hedged / neutral / strong). Dữ liệu là bản tĩnh xuất từ seed tự viết trong `apps/backend/src/aprkb/seeds/`, không gọi API và không đăng nhập. Khi không có JS, slot hiện frame mặc định.

Các slot đã deal và các lần redraw:

| Slot | Deal | Quyết định | Lý do |
|---|---|---|---|
| Hero | Headline across two fields | Giữ | Hai field phẳng gặp nhau ở đường seam cứng: hình học, không trang trí |
| Sections | intro → showcase → how-it-works → list → faq → cta → footer | Giữ, đổi nội dung (xem Phase 4) | |
| Type | Boska (serif cho nước hoa, đám cưới) | **Redraw** → Switzer, sau đó đổi sang **Be Vietnam Pro** | Boska đi ngược "tối giản, học thuật". Switzer thiếu dấu tiếng Việt (xem mục Type) |
| Palette | Orange and black | **Redraw** → Black and crimson → **thay bằng màu thương hiệu: giấy + mực + teal SLRS** | Nền cam đi ngược "tối giản, học thuật". Sau đó owner quyết định giữ teal SLRS. Theo special case "existing brand" của taste skill: giữ tỉ lệ của palette (một nền, một mực, một accent dùng rất ít) và lấy màu từ thương hiệu. Không deal lại composition |
| Motion | Colour by chapter | Giữ | Header đổi ink theo chapter; không đổi màu nền giữa section |
| Photos | Bộ "People" (picsum) | Không dùng làm ảnh chính | Ảnh người ngắm biển không liên quan chủ đề. Dùng ảnh lưu trữ thật từ open collections (Phase 4) |

> Ghi chú trung thực: do lệnh chạy trong vòng lặp, palette và type mỗi thứ bị redraw hai lần, nên `taste/landing-sheet.md` đang ghi lần thứ hai (Big Shoulders / Public Sans; Tobacco and olive). Với type, kế hoạch **dùng kết quả lần redraw thứ nhất** (Switzer). Big Shoulders là chữ biển hiệu đô thị, xa brief hơn. Với palette, cả hai lần redraw đều không dùng: owner chọn giữ teal SLRS.

### App: `achromatic-ledger`, seed 436108652, `--keep palette,type`

Deal 2 option (`achromatic-ledger`, `editorial-greeting`). Chọn `achromatic-ledger` vì staff dùng trong phiên dài (duyệt queue, tra từ). Chrome không có màu, chỉ dữ liệu chính có một hue, nên màn hình dày chữ vẫn đọc được lâu.

- **Move gốc:** chrome không có màu thương hiệu. Primary action màu gần đen. Phần dữ liệu chính của mỗi màn mang hue duy nhất (ở sản phẩm này là **slot trong frame**), dưới 1% số pixel.
- **Sai lệch có chủ đích (quyết định owner):** teal SLRS `#176b8f` là hue duy nhất. Nó xuất hiện ở ba chỗ, và chỉ ba chỗ: (1) **một** nút primary trên mỗi màn, cho việc chính của màn đó; (2) trạng thái active của nav, là pill xám kèm icon và nhãn màu teal; (3) slot trong frame. Mọi nút khác là secondary (grey pill) hoặc ghost. Không tô teal lên card, nền, tab, header hay vùng lớn. Ngân sách: khoảng 3% số pixel. Sheet liệt "brand-coloured primary button" vào off-style, nên report phải ghi sai lệch này. Nếu `inspect.mjs` WARN về màu thì giải thích bằng quyết định này, không bỏ qua.
- **Shell:** deal ra "No sidebar". **Redraw** → **Open plane**, vì sản phẩm có 11 đích và sheet nói "No sidebar" chỉ dành cho sản phẩm ít đích.
- **Face:** nền blue-grey kiểu sổ cái `#f2f4f7` thay `#f8f8f8`. Tông này hợp với teal; slot teal là chữ ký thị giác.
- Pattern màn hình: `inbox` → Inbox triage (3 vùng); `settings` → Settings two columns; `list` và `detail` không có pattern trong library, dựng theo rule của app-screens.

## Hướng thiết kế (cập nhật 2026-11-04)

**Hướng chính: Refined Editorial Workspace.** Thẩm mỹ biên tập học thuật kết hợp công cụ nghiên cứu hiện đại. Sản phẩm phải giống một không gian tham khảo học thuật được thiết kế cẩn thận, không giống một dashboard SaaS chung chung, và cũng không phải một giao diện neo-brutalist cứng nhắc. Hướng này **thay** cho "Minimalism & Geometric" làm hướng chính. Chữ "geometric" chỉ còn là một nguyên tắc con (bố cục chính xác, căn lề chặt), không còn là mô tả của cả giao diện.

Lý do đổi: bản làm theo hướng cũ (radius 4px, ledger không màu, nhiều thẻ bao nhau) cho cảm giác cứng và phẳng; owner thấy card và nút "vuông vức quá" và nhiều màn "sơ sài". Hướng mới giữ cấu trúc và độ chính xác nhưng mềm hơn ở lớp bề mặt, và để chữ, khoảng trắng và thứ bậc tổ chức nội dung trước khi dùng viền hay thẻ.

### Nguyên tắc

1. **Chính xác và hình học ở lớp bố cục.** Lưới 12 cột, mọi cạnh rơi vào đường cột, căn lề chặt. Hình học đến từ cấu trúc, không từ họa tiết.
2. **Chữ, khoảng trắng và thứ bậc đi trước viền và thẻ.** Muốn tách hai nhóm, dùng khoảng cách, tiêu đề hoặc bước đổi tông trước; chỉ khi không đủ mới thêm bề mặt.
3. **Không lồng thẻ, không viền thừa.** Một vùng nội dung là một panel, trong panel chia bằng tiêu đề và khoảng cách, không đặt thêm thẻ có viền bên trong. Một bề mặt chỉ có **một** trong hai: viền hoặc bước đổi tông, không cả hai.
4. **Bảng dữ liệu dày nhưng dễ quét.** Tiêu đề cột nhỏ, hàng 36 đến 40px, cột chính nổi hơn cột phụ, số căn phải và `tabular-nums`, trạng thái chọn và hover bằng tông nền. **Hàng bảng không bo góc riêng thành thẻ.**
5. **Bề mặt và viền kiềm chế, tinh tế.** Viền một pixel màu rất nhạt, bóng chỉ cho thứ nổi (menu, dialog, popover). Nền trang `--ground`, panel `--surface`.
6. **Giữ teal và giọng học thuật.** Teal SLRS `#176b8f` chỉ ở: tối đa một nút primary mỗi màn, nav active, slot. Serif (Newsreader) chỉ cho ngôn ngữ đang được nghiên cứu: phrase, câu ví dụ, headword.
7. **Pill chỉ cho badge, tag và chỉ báo trạng thái gọn.** Nút, ô nhập, panel không dùng pill.
8. **Landing tách biệt với workspace.** Landing giữ giọng biên tập đậm (giấy, mực, chữ lớn, ảnh lưu trữ); workspace sau đăng nhập mềm và dày dữ liệu hơn. Hai bên dùng chung font, màu thương hiệu và chữ ký "slot", nhưng không dùng chung bố cục hay thang bán kính.

### Bán kính (thang ba bậc, thay cho "một radius duy nhất")

| Thành phần | Bán kính | Token |
|---|---|---|
| Card và panel lớn, dialog, sheet, popover, command | khoảng 8px | `--radius-panel` |
| Input, select, textarea, button, toggle item | khoảng 6px | `--radius-control` |
| Hàng bảng | 0 (không bo; hover và selected là dải tông phẳng) | không có |
| Badge, tag, chỉ báo trạng thái gọn | pill (`9999px`) | `--radius-pill` |
| Slot trong frame | nhỏ, như hiện nay | `--radius-chip` |
| Landing | xem mục cần duyệt bên dưới | |

Không áp một bán kính giống nhau cho mọi thành phần nếu điều đó làm mất thứ bậc: panel mềm hơn control một nấc, control mềm hơn dải hàng bảng, pill chỉ dành cho nhãn.

### Cần owner duyệt trước khi làm

1. **Landing có đổi bán kính không?** Hiện nút và khung ở landing là 0. Đề xuất giữ 0 cho nút, ảnh và field (giọng biên tập), nhưng khung giao diện xem trước trong hero dùng 8px như workspace. Cần chốt.
2. **Slot trong frame:** giữ 2px (chữ ký sắc nét) hay nâng lên 4px cho hợp với control 6px. Đề xuất giữ 2px.
3. **Tabs, toggle group, toggle item:** tab kiểu gạch chân vẫn không bo; toggle item theo control (6px). Đề xuất như vậy.
4. **Menu con:** mục trong dropdown, select, command bo 4px, bản thân menu theo panel 8px. Đề xuất như vậy.
5. **Phạm vi làm lại bề mặt:** áp dụng thang bán kính là một thay đổi nhỏ ở `components/ui` và token; còn gỡ thẻ lồng nhau và giảm viền ở từng màn (ví dụ Library chi tiết có bốn thẻ, Vocabulary có hai thẻ liền nhau) là phần việc lớn hơn. Đề xuất tách thành **Phase 08** (bề mặt và thứ bậc), làm theo đợt như Phase 05, không gộp vào polish.
6. **Ghi nhận sai lệch với taste skill:** skill yêu cầu một bán kính duy nhất và hạn chế đường kẻ; hướng mới dùng thang ba bậc và viền nhạt có kiểm soát. Cần ghi vào ADR 0011 (sửa phần "Deviations") sau khi duyệt.
7. **Chế độ tối:** viền và bề mặt cần bộ giá trị riêng. Đề xuất dựng cùng lúc với Phase 08.

## Ngôn ngữ thiết kế

### "Geometric" nghĩa là gì ở đây (nguyên tắc con của Refined Editorial Workspace)

Taste skill cấm hình trang trí, hairline grid, crosshair, crop mark. Vì vậy tính hình học **đến từ cấu trúc, không đến từ họa tiết**:

- **Slot là hình khối duy nhất.** Một khối chữ nhật đặc, cao đúng một line-height, nằm trên baseline của dòng chữ. Đó là chữ ký thị giác của cả sản phẩm, từ hero landing tới thẻ phrase trong app.
- **Field phẳng, seam cứng.** Các section là các field màu đặc, gặp nhau ở cạnh ngang thẳng. Không gradient, không blur.
- **Lưới 12 cột nghiêm ngặt.** Mọi cạnh trái phải rơi vào đường cột, nhưng không vẽ đường lưới ra.
- **Góc bo có thang bậc.** App dùng thang ba bậc (panel 8px, control 6px, pill cho nhãn, hàng bảng không bo), xem mục [Bán kính](#bán-kính-thang-ba-bậc-thay-cho-một-radius-duy-nhất). Landing giữ góc vuông theo giọng biên tập, trừ khung giao diện xem trước (chờ duyệt). Mục này thay cho "radius 0 ở landing, 4px ở app" của bản đầu.
- **Kiểu chữ có tỉ lệ rõ:** to rất to, nhỏ vừa đủ, không có cỡ ở giữa.

### Tính học thuật

- **Serif chỉ có một việc:** hiển thị *ngôn ngữ đang được nghiên cứu*, tức phrase frame, câu ví dụ, headword của lemma. Toàn bộ UI dùng Be Vietnam Pro (Switzer đã bị bỏ vì thiếu dấu tiếng Việt). Nhờ đó người dùng phân biệt được ngay đâu là nội dung học thuật, đâu là giao diện (app-screens §13 cho phép "a second typeface with one job").
- Entry từ điển dựng như trang từ điển in: headword lớn, nhãn từ loại, family, ví dụ, provenance.
- Provenance và trạng thái licence luôn hiện cạnh nội dung (fail closed, theo `EVIDENCE_CONTRACT.md`).
- Ảnh trên landing là ảnh lưu trữ thật của thế giới học thuật, có ghi credit (Phase 4).

### Token

```css
/* Brand — teal SLRS, giữ theo quyết định owner. Chỉ dùng cho: CTA/primary, nav active, slot.
   Không bao giờ phủ diện rộng (nền section, card, header, tab). */
--brand: #176b8f;        --brand-hover: #125672;  --brand-ink: #ffffff;
--brand-tint: #eaf5f8;   /* chỉ làm nền slot */

/* Landing — tỉ lệ của palette đã deal: field giấy ở trên, field mực ở dưới, teal rất ít.
   Field dưới của hero là mực, KHÔNG phải teal. */
--paper: #efefef;   --ink: #0a0a0a;   --surface-dark: #151515;
--muted: #5c5c5c;   /* trên giấy; #8c8c8c chỉ dùng trên nền mực */
--accent: var(--brand);       /* nút hành động (nền teal, chữ trắng) và slot */
--accent-on-dark: #5fb4cc;    /* chữ hoặc slot teal đặt trên field mực */

/* App — achromatic-ledger + defaults app-screens §9.5, nền blue-grey */
--ground: #f2f4f7;  --surface: #ffffff;  --raised: #f9f9f9;  --active: #eeeeee;
--border: #e8e8e8;  --rule: #f2f2f2;     --control: #d1d5db;
--text: #111111;    --muted: #5f6368;    --faint: #6b6b6b;
--primary: var(--brand);      /* MỘT nút primary trên mỗi màn */
--secondary: #e5e5e5;         /* các nút khác: grey pill, chữ --text */
--nav-active-bg: #ececec;  --nav-active-ink: var(--brand);
--slot: #125672;    --slot-bg: var(--brand-tint);
/* Bán kính (cập nhật 2026-11-04, chờ duyệt mục 1 đến 4 ở trên; hiện code vẫn dùng --radius: 4px) */
--radius-panel: 8px;     /* card, panel, dialog, sheet, popover */
--radius-control: 6px;   /* input, select, textarea, button, toggle item */
--radius-pill: 9999px;   /* badge, tag, chỉ báo trạng thái */
--radius-chip: 2px;      /* slot trong frame */
/* Hàng bảng: không có bán kính */
--fs-title: 24px; --fs-section: 16px; --fs-body: 14px; --fs-small: 12px;

/* Dark: true-neutral theo §9.5 (#000/#111/#222), không navy. */
--brand-dark: #5fb4cc;  /* primary dark: nền #5fb4cc, chữ #0a0a0a */
--slot-dark: #5fb4cc;   --slot-bg-dark: #13283a;
```

Contrast đã đo (WCAG): teal trên trắng 5.94, trên giấy 5.16, trên nền app 5.39; chữ trắng trên nút teal 5.94; slot `#125672`/`#eaf5f8` 7.28; `#5fb4cc` trên `#0a0a0a` 8.38, trên `#111` 7.99; slot dark 6.38. Nút teal đặt trên field mực có độ tương phản cạnh 3.33, đạt ngưỡng 3:1 cho thành phần không phải chữ. Nhãn trên nút vẫn là chữ trắng 5.94.

Ánh xạ sang biến shadcn (`--background`, `--foreground`, `--primary`, `--muted-foreground`, `--border`, `--ring`, `--radius`...) làm ở Phase 01. Lỗi dùng đỏ `#c4242a` (5.78 trên trắng), luôn kèm chữ và pill tint `#ffedea`/`#831c1e`. Vì đỏ khác hẳn teal nên không lẫn với slot. Focus ring dùng `--text`, không dùng teal, để ring không bị nhầm với trạng thái active.

### Type

- **Be Vietnam Pro** (OFL, `@fontsource/be-vietnam-pro`): 400/500/600, nạp các file `400.css`/`500.css`/`600.css` (gồm subset latin, latin-ext, vietnamese theo `unicode-range`).
- **Newsreader** (OFL, `@fontsource-variable/newsreader`): chỉ dùng cho phrase/câu ví dụ/headword.
- Landing: các bước cỡ chữ lấy theo sheet (`--step-small` … `--step-head`), display tracking −0.04em, leading 0.95. App: cỡ cố định 12/14/16/24px, số dùng `tabular-nums`.
- Không monospace ngoài ID, key và code thật.
- **Tiếng Việt về sau:** cả hai font phải có dấu tiếng Việt. Newsreader có subset `vietnamese`. Không để trình duyệt tự fallback từng glyph.
- **Vì sao không dùng Switzer (đo ngày 2026-11-03 bằng fontTools):** Switzer thiếu 46/52 chữ có dấu tiếng Việt (thiếu `ơ ư` và toàn bộ `U+1EA0–1EF9`). Trình duyệt fallback từng glyph sang Arial, nên một từ bị pha hai font, và kiểm bằng mắt qua Browser MCP không phát hiện được. Đã đổi sang Be Vietnam Pro: đủ 63/63 ký tự kiểm tra ở cả 400/500/600 (đo trên `dist/assets`). Khi đổi font, luôn kiểm bằng cmap.

## Thư viện thêm vào

| Gói | Vì sao | Ghi chú |
|---|---|---|
| `tailwindcss` v4, `@tailwindcss/vite` | Bắt buộc cho shadcn | |
| shadcn/ui (copy source vào `src/components/ui`) | Yêu cầu của owner | **Radix** primitives (owner đã chốt). Theo `shadcn/rules/base-vs-radix.md`: trigger tùy biến dùng `asChild`; toast dùng `sonner` |
| `clsx`, `tailwind-merge`, `class-variance-authority` | `cn()` và variant chuẩn của shadcn | Thay `shared/ui/utils.ts` |
| `lucide-react` | Icon mặc định của shadcn | Outline 16px, stroke 1.5, màu xám (app-screens §9.4) |
| `sonner` | Toast (Radix) | |
| `motion` | Entrance và chuyển slot trên landing | Chỉ import trong chunk landing (lazy route) |
| `@fontsource-variable/newsreader` | Serif tự host | |

Không thêm: GSAP, Lenis/smooth scroll, thư viện chart (app-screens dùng `assets/charts.js` hoặc SVG riêng nếu cần).

## Phase

| Phase | Nội dung | Phụ thuộc |
|---|---|---|
| [00](phase-00-baseline-and-tooling.md) | Nhánh mới, chụp "before", cài Browser MCP, bản build `inspect` tự đăng nhập để đo route staff | — |
| [01](phase-01-foundation.md) | Tailwind v4, shadcn init, token, font, theme, cùng tồn tại với CSS cũ | 00 |
| [02](phase-02-components.md) | Bộ component shadcn đã chỉnh variant + component miền (PhraseFrame, Provenance...) + trang `/dev/ui` | 01 |
| [03](phase-03-shell-and-routes.md) | Shell "open plane", nhóm nav, đổi route `/` → landing, `/app`, `/signin` | 02 |
| [04](phase-04-landing.md) | Landing theo run trang của taste skill (bước 1–10) | 02, 03 |
| [05](phase-05-app-screens.md) | Làm lại 11 màn theo 4 đợt, mỗi màn qua gate `--app` | 03 |
| [06](phase-06-cleanup-verification.md) | Xóa CSS cũ, a11y, hiệu năng, so sánh before/after, cập nhật docs/ADR | 04, 05 |
| [07](phase-07-polish.md) | Polish: tăng mật độ thông tin, empty state, nhịp làm việc cho các màn. Chấm điểm trước và sau bằng critique | 05, 06 |

Phase 04 và 05 chạy song song được sau Phase 03.

## Định nghĩa "xong"

- `inspect.mjs`: **0 FAIL** ở 1440px (`--widths 1440`) trên bản production build (`vite build && vite preview`). Landing dùng chế độ trang; từng app screen dùng `--app`. Mỗi WARN còn lại có một câu giải thích trong report.
- `lint.mjs` (và `--app` cho app) sạch trên `apps/web/src`.
- `pnpm --dir apps/web run lint`, `typecheck`, `build` pass. Không chạy `test:e2e` (quyết định owner #5).
- Đã click qua mọi link, form, menu từng chạy trước đây bằng Browser MCP, ở desktop. Kết quả ghi theo từng route vào report của phase: đã thử gì, kết quả ra sao, lỗi console nếu có. Đây là thứ thay cho e2e, nên không được chỉ ghi "đã test".
- Contrast chữ ≥ 4.5:1 (NFR-08), focus nhìn thấy được, làm được mọi việc bằng bàn phím, có `prefers-reduced-motion`.
- `make lint` và `make test` vẫn pass (backend không đổi, nhưng `CLAUDE.md` yêu cầu chạy).
- Mỗi PR đã qua `code-review` và đã xử lý các finding trước khi merge.
- README và ADR mới về design system frontend đã cập nhật.

## Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Preflight của Tailwind phá các trang chưa migrate | `styles.css` cũ để ngoài layer nên thắng preflight. Mỗi màn sau khi migrate gỡ class cũ và xóa phần CSS tương ứng. Phase 01 chụp lại toàn bộ màn để so sánh |
| Xung đột với nhánh vocabulary | Commit vocabulary riêng trên `feat/academic-vocabulary`; chỉ merge hoặc push khi owner yêu cầu |
| Hiển thị nội dung có bản quyền trên landing (AVL, Academic Phrasebank) | Landing chỉ dùng frame tự viết từ seed. Không hiện dòng AVL nào. Ảnh chỉ lấy licence cho phép, có credit |
| Số liệu bịa trên landing ("10,000 phrases") | Taste skill cấm proof bịa. Landing không hiện số đếm nào trừ khi lấy từ seed lúc build |
| Teal lan dần ra chrome (mỗi màn thêm một nút teal, tab teal, header teal) | Quy tắc "một primary teal mỗi màn". `code-review` và critique app-screens (câu 3) phải kiểm tra điều này. Grep `bg-primary` theo từng màn ở Phase 06 |
| Nav active (chữ teal) bị nhầm với link | Active luôn có pill xám `#ececec` đi kèm, không bao giờ chỉ có màu chữ |
| Không còn kiểm thử hồi quy tự động (đã tắt Playwright) | Mỗi PR có checklist Browser MCP theo route, ghi kết quả. `code-review` đối chiếu checklist với diff. Sau redesign, owner quyết định sửa và bật lại e2e hay xóa |
| `inspect.mjs` không đăng nhập được (profile Chrome trống), nên chỉ thấy màn sign in ở route staff | Bản build `inspect` tự gọi demo session (Phase 00, mục 2b) |
| Copy tiếng Anh hardcode khắp JSX, khó thêm tiếng Việt | Landing tách toàn bộ chuỗi ra file copy (Phase 04). App screens không bắt buộc ở redesign này |
| Bundle phình vì `motion` | Landing là lazy route; kiểm tra kích thước chunk ở Phase 06 |

## Quyết định của owner (2026-11-03)

| # | Quyết định | Ảnh hưởng tới plan |
|---|---|---|
| 1 | **Giữ teal SLRS `#176b8f`** làm màu nhận diện chính, dùng tiết chế: CTA, trạng thái active, điểm nhấn. Không phủ diện rộng, không làm giảm độ tương phản | Palette crimson bị bỏ. Token ở mục [Token](#token). App lệch khỏi move gốc của `achromatic-ledger` (primary mang màu thương hiệu), ghi lại trong report. Không deal lại direction: composition giữ nguyên, chỉ thay màu theo special case "existing brand" |
| 2 | **Radix UI** cho shadcn | `pnpm dlx shadcn@latest init` chọn Radix; dùng `asChild`, `sonner` |
| 3 | **`/` là landing công khai**; app sau đăng nhập dùng route riêng, ví dụ **`/app`** | Trang chủ staff là `/app` (thay `/home`). Các màn khác **giữ đường dẫn cũ** (`/library`, `/extract?batch=`...) để không gãy deep link, nhưng nằm trong `appLayout` có guard. Nếu muốn gom hết dưới `/app/*` thì đó là một đợt riêng, có redirect từ đường dẫn cũ (xem Phase 03) |
| 5 | **Tắt Playwright, dùng Browser MCP** để kiểm tra trên trình duyệt | Không chạy `test:e2e` và không sửa test e2e trong redesign này. File `e2e/*.spec.ts` giữ nguyên trong repo (chỉ đã sửa đường dẫn screenshot ở Phase 00). Baseline có 2/8 test fail từ trước redesign (màu chữ cũ, một chuỗi mô tả trong Writer), ghi trong audit, không phải blocker. Gate là `inspect.mjs` + checklist Browser MCP có ghi lại kết quả. `inspect.mjs` **không** phải Playwright: nó tự mở Chrome qua CDP và vẫn là gate |
| 6 | **Đổi hướng thiết kế chính sang Refined Editorial Workspace** (2026-11-04), bán kính thang ba bậc, ít thẻ lồng và viền hơn | Cập nhật Mục tiêu, [Hướng thiết kế](#hướng-thiết-kế-cập-nhật-2026-11-04) và token. **Chưa triển khai**; chờ duyệt 7 điểm trong mục đó. Dự kiến thành Phase 08 |
| 4 | **Landing tiếng Anh mặc định**, thiết kế để bổ sung tiếng Việt sau | Toàn bộ chuỗi landing nằm trong `copy.en.ts`; `<html lang>` lấy theo locale; layout chịu được chuỗi dài hơn khoảng 30%; font phải có dấu tiếng Việt (xem [Type](#type)). Chưa thêm thư viện i18n |
