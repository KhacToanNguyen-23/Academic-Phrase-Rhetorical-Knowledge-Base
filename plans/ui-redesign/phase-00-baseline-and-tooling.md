# Phase 00: Baseline và công cụ

Mục tiêu: có ảnh và số đo "before" để so sánh, có Browser MCP chạy được, và `inspect.mjs` đo được cả route staff.

**Tình trạng 2026-11-03.** Đã hoàn tất: audit ([report](../reports/261103-ui-redesign-before-audit.md)), Browser MCP (`.mcp.json`), `.gitignore`, sửa đường dẫn screenshot e2e, lint baseline (15 FAIL, 48 WARN), mục 2b auto-login và `inspect.mjs` cho mọi route ở 3 viewport.

**Về lỗi `CDP timeout: Page.enable`.** Lỗi đến từ môi trường của agent, công cụ không hỏng. Trên cùng máy, ngày 2026-11-03, `inspect.mjs --app http://127.0.0.1:4173/writer` chạy xong và ra kết quả (2 FAIL, 4 WARN, có ảnh ở 3 cỡ màn hình). Nếu agent chạy trong sandbox chặn Chrome mở cổng debug (`--remote-debugging-port`), phải xin chạy lệnh ngoài sandbox, hoặc nhờ owner/agent khác chạy rồi đưa lại đường dẫn tới `report.json` và ảnh.

## Đọc trước khi làm

- `.agents/skills/design-taste-frontend/SKILL.md`: mục "Special cases → Redesign, restyle or review" và "The run → 7. Gate"
- `.agents/skills/design-taste-frontend/references/app-screens.md`: §2.7 (The check)
- `.agents/skills/redesign-existing-projects/SKILL.md`: toàn bộ (checklist audit)
- `.agents/plugins/skills/skills/frontend-mindset/references/review-checklist.md`

## Việc

1. **Nhánh.** Commit phần vocabulary trên `feat/academic-vocabulary`; chỉ merge hoặc push khi owner yêu cầu. Nhánh Phase 00 là `feat/ui-redesign`.
2. **Before.** (Đã có snapshot Browser MCP và lint baseline. Còn thiếu số đo của inspector.) Chạy backend (`make up migrate seed run`), chạy web (`npm --prefix apps/web run build && npm --prefix apps/web run preview`), đăng nhập demo, rồi chụp từng route:
   ```bash
   S=.agents/skills/design-taste-frontend
   node $S/scripts/lint.mjs --app apps/web/src > .taste-skill/before/lint.txt
   node $S/scripts/inspect.mjs --app http://127.0.0.1:4173/library --out .taste-skill/before/library
   # lặp cho: / /phrasebank /vocabulary /journals /inbox /gold /extract /import /admin /playground /writer
   ```
   Route công khai (`/writer`, và sau này `/`, `/signin`) đo được bằng bản build thường. Route staff cần bản build ở mục 2b.

2b. **Bản build `inspect` tự đăng nhập.** `inspect.mjs` mở Chrome với profile trống. Phiên đăng nhập lại lưu trong `sessionStorage`, nên mọi route staff chỉ hiện màn sign in. Thêm:
   - `apps/web/.env.inspect` chứa `VITE_INSPECT_AUTOLOGIN=1`. File này được commit vì không chứa secret.
   - Trong `AuthProvider`: nếu `import.meta.env.MODE === "inspect"`, `VITE_INSPECT_AUTOLOGIN === "1"` và chưa có key trong `sessionStorage`, tự gọi `demoLogin()` một lần. Trong lúc chờ thì giữ `loading`, để inspector không chụp màn sign in.
   - Script `"build:inspect": "tsc -b && vite build --mode inspect --outDir dist-inspect"` và `"preview:inspect": "vite preview --outDir dist-inspect --port 4174"`. Thêm `dist-inspect/` vào `.gitignore`.
   - Vì sao an toàn: `vite build` thường chạy mode `production`, nên nhánh code này bị loại khỏi bundle. Endpoint `POST /v1/auth/demo-session` của backend chỉ nhận request từ loopback. Phải kiểm tra lại bằng cách grep `demo-session` trong `dist/` sau `npm run build`: không được có kết quả.
   - Đo: `node $S/scripts/inspect.mjs --app http://127.0.0.1:4174/library --out .taste-skill/before/library`, lặp cho từng route staff.

   Nếu chưa làm được 2b thì route staff chụp bằng Browser MCP vào `.taste-skill/before/<route>/`, và report ghi rõ là **chưa có số đo của inspector** cho route đó.
3. **Audit** bằng checklist `redesign-existing-projects` và `frontend-mindset/references/review-checklist.md`. Ghi kết quả vào `plans/reports/261103-ui-redesign-before-audit.md`: lỗi theo màn, kèm số đo của inspector.
4. **Browser MCP cho Claude Code.** Hiện chỉ có trong Codex. Thêm ở scope project:
   ```bash
   claude mcp add browsermcp --scope project -- npx @browsermcp/mcp@latest
   ```
   Cài extension Browser MCP trên Chrome, bấm Connect ở tab cần test. Kiểm tra bằng cách mở `http://127.0.0.1:5173/writer` rồi lấy snapshot.
5. **e2e.** (Đã làm.) Trong `e2e/*.spec.ts`, thay đường dẫn screenshot hardcode `C:/Users/khact/...` bằng `process.env.E2E_SCREENSHOT_DIR ?? "test-results/screens"`. Owner đã tắt Playwright, nên **không chạy** `test:e2e` và không sửa 2 test đang fail.
6. `.taste-skill/` vào `.gitignore` (screenshot, không commit). `plans/ui-redesign/taste/` thì commit.

## Xong khi

- Có thư mục `before` cho mọi route và file audit.
- Browser MCP lấy được snapshot trang local.
- `inspect.mjs` có `report.json` và ảnh ở 3 cỡ cho mọi route: route công khai đo bằng build thường, route staff đo bằng build `inspect`. Route nào chỉ có ảnh Browser MCP thì report phải ghi rõ.
- Build thường không chứa nhánh tự đăng nhập: grep `demo-session` trong `dist/` không có kết quả.
- Đã chạy `code-review` trên PR (`.gitignore`, `.mcp.json`, đường dẫn e2e, build `inspect`).

Không thuộc phạm vi Phase 00: sửa 15 FAIL của lint baseline, các lỗi 403/404 ở `/gold`, `/extract`, `/phrasebank` (xử lý trong Phase 05), và 2 test e2e đang fail.

Lưu ý: nhánh `feat/ui-redesign` đã được tạo từ working tree đang dở (còn thay đổi chưa commit của vocabulary và của các file `LoginPage.tsx`, `WriterContextForm.tsx`, `WriterValidation.tsx`, `shared/ui/index.tsx`, đã sửa từ trước khi có plan). Trước khi mở PR đầu tiên, commit phần vocabulary riêng để PR redesign chỉ chứa thay đổi của redesign; chỉ merge hoặc push khi owner yêu cầu.
