# Phase 01: Nền tảng (Tailwind v4, shadcn, token, font, theme)

Mục tiêu: cài shadcn thật, đặt token mới, và giữ mọi trang cũ hiển thị như trước.

## Đọc trước khi làm

- `.agents/skills/shadcn/SKILL.md`, `cli.md`, `customization.md`, `rules/base-vs-radix.md`, `rules/styling.md`
- `.agents/skills/design-taste-frontend/references/app-screens.md`: §9 (Type and colour, gồm §9.5 Default tokens)
- `.agents/skills/design-taste-frontend/references/type.md` (nạp font) và `colour.md` (vai trò màu, dark)
- `plan.md` của plan này: mục Token và Type. Đây là nguồn giá trị duy nhất; **không** lấy font/màu từ `taste/landing-sheet.md`

## Việc

1. **Tailwind v4.** `pnpm add -D tailwindcss @tailwindcss/vite`. Thêm `tailwindcss()` vào `plugins` trong `vite.config.ts`. Alias `@` đã có sẵn.
2. **shadcn init** trong `apps/web`: `npx shadcn@latest init`, chọn **Radix** (owner đã chốt), CSS `src/app/globals.css`, components ở `src/components/ui`, `cn` ở `src/lib/utils.ts`. Kiểm tra `components.json` bằng `npx shadcn@latest info --json`.
3. **Token** trong `globals.css`. Khai báo token gốc như ở mục Token của `plan.md`, rồi ánh xạ vào biến shadcn dùng `@theme inline`:
   - `--background: var(--ground)`, `--card: var(--surface)`, `--foreground: var(--text)`, `--muted-foreground: var(--muted)`
   - `--primary: var(--brand)` (teal `#176b8f`), `--primary-foreground: #fff`. Dark: `#5fb4cc` với chữ `#0a0a0a`
   - `--sidebar-primary` và `--sidebar-accent`: nền pill xám `#ececec`, chữ teal (nav active)
   - `--secondary: #e5e5e5`, chữ đi kèm là `--text` (đúng "grey pill" làm secondary của sheet)
   - `--border: var(--border)`, `--input: var(--control)`, `--ring: var(--text)`
   - `--radius: 4px`
   - `--destructive: #c4242a`
   - Token riêng: `--slot`, `--slot-bg`, `--font-sans: "Be Vietnam Pro"`, `--font-serif: "Newsreader"`
   - Dark: `.dark` và `[data-theme="dark"]` cùng nhận bộ true-neutral của app-screens §9.5.
4. **Font.** `pnpm add @fontsource/be-vietnam-pro @fontsource-variable/newsreader`. Import `@fontsource/be-vietnam-pro/{400,500,600}.css` trong `globals.css`. Ban đầu dùng Switzer nhưng đã bỏ vì thiếu dấu tiếng Việt (xem mục Type trong `plan.md`). Kiểm dấu bằng cmap (fontTools) trên file trong `dist/assets`, không chỉ nhìn bằng mắt.
5. **Theme.** Giữ hành vi của `shared/lib/theme.ts` (mặc định light, nhớ trong sessionStorage). Mỗi lần đổi theme, cập nhật đồng thời `data-theme` và class `.dark`.
6. **Cùng tồn tại.** `main.tsx` import `globals.css` trước `styles.css`. `styles.css` cũ để ngoài layer nên thắng preflight trên các trang chưa migrate. Đổi `body` cũ sang biến mới chỉ khi trang đó đã migrate.
7. **`cn`.** `shared/ui/utils.ts` re-export `cn` từ `@/lib/utils`, để import cũ không vỡ.
8. Thêm `.taste-skill/` vào `.gitignore` nếu Phase 00 chưa làm.

## Xong khi

- `lint`, `typecheck`, `build` pass.
- So ảnh mọi route với `before` (Browser MCP): không có trang nào vỡ layout. Font khác là chấp nhận được, layout vỡ thì không.
- Đã chạy `code-review` trên PR và đã xử lý các finding.
