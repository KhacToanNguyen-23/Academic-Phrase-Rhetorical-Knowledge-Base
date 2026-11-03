# Phase 04: Landing page

Làm đúng run trang của taste skill (`SKILL.md`, bước 1–10). Direction: [taste/landing-sheet.md](taste/landing-sheet.md). Đọc lại file đó trước mỗi section. **Không** dùng `draw.mjs --show` (nó in §3 Type và §4 Colour đã bị thay) và **không** dùng `--redraw` (nó ghi đè sheet). Font và màu lấy từ mục Token/Type của `plan.md`.

## Đọc trước khi làm

- `.agents/skills/design-taste-frontend/SKILL.md`: toàn bộ (run, house rules, laws)
- `.agents/skills/design-taste-frontend/references/`: `copy.md` (bước 2, 5), `type.md`, `colour.md`, `layout.md`, `imagery.md` (bước 6), `motion.md` (bước 9), `critique.md` (bước 8), `tells.md`
- `taste/landing-sheet.md` của plan này (đọc phần cảnh báo ở đầu file)
- `.agents/plugins/skills/skills/frontend-mindset/references/responsive-performance.md` (LCP, ảnh responsive)

## 1. Inventory (những thứ chỉ sản phẩm này có)

1. Phrase frame có slot `[finding]`, `[method]`
2. Rhetorical move theo IMRaD (gap, method, finding, limitation)
3. Độ mạnh claim: hedged / neutral / strong (EvidencePolicy)
4. Cluster theo thì của động từ: khác thì là khác cluster
5. Phrase đặc trưng của *một* journal so với phrasebank gốc
6. Academic Vocabulary: lemma, word family, rank (không hiện nội dung AVL)
7. Provenance và licence fail closed: không rõ quyền thì khóa
8. Hai vòng review của editor trước khi vào bank; pattern version append-only
9. Bài báo nhập từ SLR repository
10. Đồ in trong thế giới này: trang tạp chí khoa học, trang từ điển, ngăn kéo thẻ thư mục, khay chữ in

## 2. Argument (claim → bằng chứng → section)

| Section (blueprint) | Claim | Bằng chứng |
|---|---|---|
| Hero (two fields) | Câu đúng cho mọi claim | Headline có slot sống |
| intro (headline crossing onto a photograph) | Phrase là khung, slot để ngỏ | Ảnh lưu trữ trang tạp chí + câu giải thích |
| showcase (object in front of type) | Phrase được xếp theo move của bài báo | Chữ xếp chồng "Introduction / Methods / Results / Discussion"; vật thể là một **mảnh UI thật** (`data-ui`) của thẻ PhraseFrame |
| how-it-works (one verb at a time) | Mỗi phrase qua 4 bước | 4 panel 100svh: **Import · Mine · Review · Recommend**, mỗi panel một ảnh lưu trữ và một câu |
| list (statement, table pushed right) | Biết bắt đầu từ đâu | Bảng 6–8 dòng: Library, Phrasebank, Vocabulary, Journals, Writer, Review. Mỗi dòng: tên, nội dung, link |
| faq (wide heading, indented questions) | Nguồn gốc rõ ràng | 6 câu hỏi, dựng bằng `<details>` |
| cta (question at both edges) | Đọc hay viết? | Hai nút: "Browse the phrasebank" / "Open the writer" |
| footer (invitation over a cropped name) | — | Chữ "wordbank" bị cắt ở mép dưới; credit ảnh; câu provenance |

## 3. Copy deck (bản nháp, tiếng Anh; mọi headline tối đa 2 dòng, khoảng 32 ký tự)

**Sẵn sàng cho tiếng Việt (quyết định owner):** tiếng Anh là mặc định. Toàn bộ chuỗi của landing (headline, câu phụ, nhãn nút, FAQ, alt ảnh, credit, tên các move) nằm trong `src/features/landing/copy.en.ts`, export một object có kiểu `LandingCopy`. JSX không chứa chuỗi hiển thị nào. Sau này chỉ cần thêm `copy.vi.ts` cùng kiểu đó. Frame trong `frames.json` là nội dung học thuật tiếng Anh, giữ nguyên ở mọi locale. `<html lang>` lấy theo locale đang dùng. Headline phải còn tối đa 2 dòng khi chuỗi dài hơn khoảng 30% (tiếng Việt thường dài hơn), nên dùng `text-wrap: balance` và không cố định chiều rộng theo chuỗi tiếng Anh. Chưa thêm thư viện i18n.

- **h1:** "The right ▮ for every claim". Slot ▮ hiện một frame sống, ví dụ *suggests that*. Tên truy cập được: "The right phrasing for every claim".
- **Câu dưới h1:** "Academic Wordbank is a phrasebank and academic vocabulary dictionary, built from licensed journal articles."
- **Action chính:** "Open the phrasebank" (chưa đăng nhập thì sang `/signin?next=/phrasebank`).
- intro: "Phrases with the slots left open"
- showcase heading: dòng chữ đậm nhất là "Results"; khối facts nói một pattern chứa những gì (move, slot, độ mạnh, provenance).
- how-it-works: bốn động từ trên là heading; mỗi panel có một câu, ví dụ Import: "Only articles whose licence allows mining are read."
- list: "Where each kind of phrase lives"
- faq: "Where the phrases come from". Câu hỏi: Is this the Academic Phrasebank? (No: every seed phrase is self-authored) · Why is an entry locked? · What is a slot? · How is a journal's own phrasing found? · Can the writer invent a citation? (No) · Who approves a phrase?
- cta: "Read or write?"
- footer: "Find the phrase your journal uses"

Không có số liệu, khách hàng hay trích dẫn bịa. Nếu cần một con số, nó phải tính từ seed lúc build.

## 4. Live thing

`ToggleGroup` 4 move nằm ngay dưới câu phụ của hero. Bấm một move thì slot đổi frame (dùng `motion`, chỉ transform/opacity, 240ms) và hiện nhãn độ mạnh. Dữ liệu là `src/features/landing/frames.json`, xuất từ seed tự viết (script `npm run gen:landing-frames` đọc file seed của backend). Không có JS: hiện frame mặc định. Có reduced motion: đổi frame không trượt.

## 5. Ảnh (sàn của inspector: ≥ 4 ảnh thật)

Tìm trong open collections, chỉ lấy licence cho phép thương mại:

```bash
S=.agents/skills/design-taste-frontend
node $S/scripts/assets.mjs "Philosophical Transactions 1665 page"
node $S/scripts/assets.mjs "Johnson dictionary 1755 page"
node $S/scripts/assets.mjs "library card catalog drawers"
node $S/scripts/assets.mjs "printing type case compositor"
node $S/scripts/assets.mjs "reading room library engraving"
node $S/scripts/assets.mjs --video "printing press letterpress"
node $S/scripts/assets.mjs --get <ref>      # tải về src/features/landing/assets/
node $S/scripts/assets.mjs --credits         # dòng credit cho footer
```

Một cách xử lý ảnh cho cả bộ: grayscale, contrast cao, góc vuông. Ảnh trong slot của hero (nếu dùng ảnh thay frame) là một dải hẹp cắt từ trang tạp chí. Mảnh UI thật trong showcase được tính là ảnh. Ảnh lưu trữ chỉ là thế giới quanh sản phẩm, không bao giờ trình bày như nội dung của sản phẩm.

## 6. Dựng

`src/features/landing/` là lazy route. Thứ tự: token → hero (desktop 1440px) → từng section theo blueprint → ảnh → live thing → frame/fullness → states và semantics. Mỗi section là một chapter màu giấy hoặc mực (giấy / mực / giấy / mực...). **Không có field nào màu teal.** Field dưới của hero là mực. Teal chỉ xuất hiện ở nút hành động, ở slot sống trong headline và ở item đang chọn của `ToggleGroup`. Trên field mực, chữ và slot teal dùng `--accent-on-dark` (`#5fb4cc`); nút teal giữ nền `#176b8f` với chữ trắng. Header đổi ink theo chapter bằng IntersectionObserver, chuyển màu 300ms. Nút dùng shadcn `Button` (variant landing, radius 0, 56px); FAQ dùng `<details>`, chỉ style lại, không bọc Accordion để còn chạy khi không có JS.

## 7–9. Gate, nhìn, chuyển động

```bash
node $S/scripts/lint.mjs apps/web/src/features/landing
pnpm --dir apps/web run build && pnpm --dir apps/web run preview
node $S/scripts/inspect.mjs http://127.0.0.1:4173/ --widths 1440 --out .taste-skill/after/landing
```

- Sửa mọi FAIL. Mở **mọi** screenshot, critique theo `references/critique.md` (14 lượt, có điểm), sửa 3 lỗi nặng nhất. Tối đa 3 vòng.
- Motion: signature move "colour by chapter"; entrance so le 60–90ms cho heading → text → ảnh; feedback trên mọi control; một ảnh chuyển động (scale chậm). Inspector đòi ≥ 8 phần tử chuyển động. Mọi chuyển động có fallback reduced-motion.
- Browser MCP: test live thing bằng chuột và bàn phím, trên desktop. Tắt JS để kiểm tra fallback.

## 10. Report

Ghi vào `plans/reports/261103-landing-report.md`: direction và seed, các lần redraw kèm lý do, câu ý tưởng, live thing, điểm critique vòng cuối và chỗ còn thiếu, credit từng ảnh/clip, nội dung mẫu cần thay trước khi dùng thật.

Sau đó chạy `code-review` trên PR landing và xử lý các finding trước khi merge.

## Kết quả (2026-11-04)

Đã làm xong, xem `plans/reports/261104-landing-report.md`. Khác spec: không dùng `motion` (chính sách `minimumReleaseAge` của pnpm chặn khi thêm gói; dùng CSS transition và IntersectionObserver), frame viết tay trong `frames.ts` (không có script `gen:landing-frames`), và không có no-JS fallback vì app là SPA.
