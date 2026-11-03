# Phase 02: Bộ component

Mục tiêu: một bộ component shadcn đã chỉnh theo house rules, cộng các component miền, xem được hết ở một trang `/dev/ui`.

## Đọc trước khi làm

- `.agents/skills/shadcn/SKILL.md` và cả 5 file `rules/` liên quan: `styling.md`, `composition.md`, `forms.md`, `icons.md`, `base-vs-radix.md`
- `.agents/skills/design-taste-frontend/references/app-screens.md`: §7 (Tables), §8 (Forms), §9.4 (Surfaces, radius, icons), §11 (States), §13 (House rules for app screens)
- `.agents/plugins/skills/skills/frontend-mindset/references/motion-interaction.md` (8 trạng thái, focus, dropdown, modal) và `copy.md` (nhãn nút, empty state)
- `.agents/plugins/skills/skills/minimalist-ui/SKILL.md`: **chỉ** mục Keystroke Micro-UIs (`<kbd>`). Bỏ qua phần pill chữ hoa, bento border, faux-OS chrome, radial gradient

## Component shadcn cần thêm

```bash
pnpm dlx shadcn@latest add button badge input textarea label field input-group select combobox \
  dropdown-menu popover command dialog alert-dialog sheet tabs toggle-group table \
  checkbox radio-group switch tooltip separator skeleton empty alert sonner \
  sidebar breadcrumb pagination scroll-area kbd spinner card
```

Trước khi viết markup riêng: `pnpm dlx shadcn@latest search <tên>` và `pnpm dlx shadcn@latest docs <component>`.

## Chỉnh variant một lần (trong `src/components/ui/*`)

| Component | Chỉnh | Nguồn rule |
|---|---|---|
| Button | `default` = nền teal `--brand`, chữ trắng, hover `--brand-hover`, không shadow. **Mỗi màn chỉ một nút `default`** (việc chính); mọi nút khác là `secondary` (grey pill `#e5e5e5`, chữ `--text`) hoặc `ghost`. Cao 32px trong app, 56px trên landing (variant `size="xl"`). Bỏ `shadow-xs`. Có `:active` scale 0.98 | Quyết định owner (teal cho CTA), app-screens §8.3 |
| Card | Bỏ shadow. Hoặc border 1px `--border`, hoặc bước tone, không dùng cả hai. Radius 4px | app-screens §9.4 |
| Badge | Pill tint nhạt + chữ đậm cùng hue, cao 20px, sentence case, **không chữ hoa có tracking** | app-screens §7.6, §13 |
| Table | Header 12px xám sentence case, không band, không zebra. Row rule 1px `--rule`. Cột số căn phải, `tabular-nums` | app-screens §7 |
| DropdownMenu, Popover, Dialog, Sheet, Tooltip | Giữ shadow (đây là các thứ "nổi"). Radius 4px | house rules |
| Tabs | Kiểu underline, không pill màu | app-screens §4.4 |
| Sidebar | Active = pill xám `#ececec`, icon và nhãn teal. Không tô nền teal, không có thanh màu bên trái. Icon 16px stroke 1.5 | Quyết định owner (teal cho active), app-screens §3.2 |
| Tabs, Badge, Card, header | **Không dùng teal.** Teal chỉ ở primary, nav active và slot | Quyết định owner: "không phủ diện rộng" |
| Input/Select | Cao 32px, border `--control`, focus ring 2px `--text` | |

## Component miền (`src/shared/ui/` → chuyển dần sang `src/components/domain/`)

- **`PhraseFrame`**: render frame có slot. Slot là khối `--slot-bg` (teal tint `#eaf5f8`) với chữ `--slot` (`#125672`), radius 2px, nằm trên baseline. Phrase dùng Newsreader. Có `aria-label` đọc được slot ("[finding]"). Đây là chữ ký thị giác dùng chung cho landing, library, phrasebank, extract, gold, writer.
- **`ProvenanceTag`** / **`LicenceStatus`**: dựa trên Badge. Trạng thái unknown hiện "Locked: licence unknown" (fail closed).
- **`EvidenceLabel`**, **`StatusBadge`**, **`SeverityBadge`**: chuyển từ `shared/ui/index.tsx` sang Badge.
- **`PageHeader`**: h1 24px (danh từ), câu mô tả 14px, khu action bên phải.
- **`DataState`**: bọc loading (Skeleton), empty (Empty), error (Alert + nút thử lại). Số 0 in là "0", thiếu giá trị in "—" (app-screens §11).
- **`DictionaryEntry`**: headword Newsreader, từ loại, family, rank, ví dụ, provenance.

## Trang `/dev/ui`

Chỉ có khi `import.meta.env.DEV || import.meta.env.MODE === "inspect"` (cùng điều kiện với demo session ở Phase 00). Route và chunk của trang **không** được có trong `dist/`; kiểm bằng `grep -r "dev/ui" dist/` ra 0 kết quả. Hiện mọi component với đủ 8 trạng thái (default/hover/focus/active/disabled/loading/error/success), light và dark. Dùng làm bàn kiểm cho `inspect.mjs --app` và Browser MCP.

## Xong khi

- `lint.mjs --app apps/web/src/components` sạch.
- `inspect.mjs --app http://127.0.0.1:4174/dev/ui --widths 1440` 0 FAIL, chạy trên `pnpm run build:inspect && pnpm run preview:inspect` (cổng 4174).
- `src/shared/ui/*` cũ vẫn còn và các trang cũ không đổi giao diện. Component mới nằm ở `src/components/ui/`, component miền ở `src/components/domain/`. Việc thay import trên từng màn làm ở Phase 05.
- Không còn `space-y-*`, không còn `dark:` thủ công, không có `className` ghi đè màu hoặc chữ (rule `shadcn/rules/styling.md`).
- Đã chạy `code-review` trên PR và đã xử lý các finding.

> Quy ước gói (owner chọn 2026-11-03): chỉ dùng **pnpm**. Thêm thư viện bằng `pnpm add`, chạy CLI bằng `pnpm dlx`, và commit `pnpm-lock.yaml`. Không tạo `package-lock.json`.
