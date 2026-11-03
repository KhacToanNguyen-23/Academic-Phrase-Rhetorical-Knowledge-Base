# Phase 06: Dọn dẹp và kiểm chứng

## Đọc trước khi làm

- `.agents/plugins/skills/skills/frontend-mindset/references/review-checklist.md`, `responsive-performance.md`
- `.agents/skills/design-taste-frontend/references/critique.md`
- `.agents/skills/design-taste-frontend/SKILL.md`: mục "Special cases → Redesign … 5. Prove it" (báo cáo before/after)

## Dọn

- Xóa `src/app/styles.css`, hoặc chỉ giữ phần không thể biểu diễn bằng utility, chuyển sang `globals.css`.
- Xóa `src/shared/ui/{button,card,input,textarea,badge,skeleton}.tsx` cũ. Import trỏ về `@/components/ui`.
- Gỡ token cũ trong `styles.css` (`--color-*`, `--shadow-*`), vì teal đã chuyển sang `--brand` trong `globals.css`. Gỡ các class không còn dùng. Kiểm tra bằng grep các tên class cũ (`ui-button`, `btn-`, `hero-`, `side-`).

## Kiểm chứng

1. Production build: `pnpm --dir apps/web run build && pnpm --dir apps/web run preview`.
2. `inspect.mjs` (landing) và `inspect.mjs --app` (mọi màn), đều với `--widths 1440`, vào `.taste-skill/after/`, 0 FAIL. Bảng so sánh before/after theo số đo của inspector.
3. `lint.mjs` và `lint.mjs --app` trên `apps/web/src`.
4. `pnpm --dir apps/web run lint && pnpm --dir apps/web run typecheck`. Không chạy `test:e2e` (quyết định owner #5). Report cuối ghi rằng e2e chưa được cập nhật theo UI mới, để owner quyết định sửa và bật lại hay xóa.
5. Browser MCP, theo checklist: mọi link trong nav; mọi form (signin, import profile, writer context, playground); mọi dropdown/select/combobox/dialog/sheet; theme light/dark (chỉ desktop); chỉ dùng bàn phím; tắt JS ở landing.
6. A11y: contrast ≥ 4.5:1 cho cả light và dark (đo lại các cặp teal ở mục Token của plan); mô phỏng mù màu (nav active phân biệt được nhờ pill xám, không chỉ nhờ màu). Kiểm tra ngân sách teal: mỗi màn đúng một nút primary teal (grep `variant="default"` hoặc Button không có variant, theo từng màn).
7a. Landing: thử thay `copy.en.ts` bằng một bản giả tiếng Việt dài hơn khoảng 30%. Headline vẫn tối đa 2 dòng ở 1440px, dấu hiển thị đúng font.
7. Hiệu năng: kích thước chunk app và chunk landing (`motion` chỉ nằm trong chunk landing), LCP của landing trên preview.
8. `make lint` và `make test` (backend không đổi, nhưng `CLAUDE.md` yêu cầu). Nếu PostgreSQL/Docker không có thì ghi rõ check nào chưa chạy.
9. `code-review` trên toàn bộ diff `feat/ui-redesign` so với `dev` trước PR cuối.

## Docs

- `doc/adr/0011-frontend-design-system.md`: chọn Tailwind v4 + shadcn, hai direction và seed, thứ tự ưu tiên skill, 4 quyết định owner ngày 2026-11-03 (teal SLRS dùng tiết chế, Radix, `/` và `/app`, tiếng Anh sẵn cho tiếng Việt), sai lệch khỏi move của `achromatic-ledger`.
- `apps/web/README.md`: cách thêm component (`pnpm dlx shadcn@latest add`), token, font, cách chạy gate taste.
- `README.md` gốc: route mới (`/`, `/signin`, `/app`).
- Report cuối: `plans/reports/` gồm số đo before/after, critique vòng cuối, credit ảnh, mock còn lại.
