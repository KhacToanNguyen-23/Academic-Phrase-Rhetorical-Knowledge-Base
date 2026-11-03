> **CẢNH BÁO — đọc trước:** §3 Type và §4 Colour bên dưới **đã bị thay thế** (đây là kết quả redraw lần hai, đã bị loại).
> Dùng Switzer + Newsreader và màu thương hiệu (giấy, mực, teal SLRS `#176b8f` dùng tiết chế) theo mục Token/Type của `../plan.md`. Không dùng crimson hay cam.
> Mọi mục khác của sheet (direction, hero, sections, motion) vẫn có hiệu lực. Không chạy `draw.mjs --redraw` nữa: lệnh đó ghi đè sheet.

# DIRECTION SHEET — The sentence is the layout
seed 568972173 · drawn 2026-11-03 · redraws: 4 · sector education · tone editorial
Brief: Academic Wordbank: an internal phrasebank and academic vocabulary dictionary that mines rhetorical phrase frames with slots from licensed journal articles, so writers can see which phrases one journal characteristically uses

| | |
| --- | --- |
| Direction | The sentence is the layout |
| Hero | Headline across two fields |
| Type | Big Shoulders / Public Sans |
| Colour | Tobacco and olive |
| Sections | intro (Headline crossing onto a photograph) → showcase (Object in front of type) → how-it-works (One verb at a time) → list (Statement, table pushed right) → faq (Wide heading, indented questions) → cta (Question at both edges) → footer (Invitation over a cropped name) |
| Motion | Colour by chapter |
| Photographs | the "People" set, as atmosphere |

This is the direction for this build. Adopt it. Do not blend it with the layout you would have made anyway,
and do not redraw because it is unfamiliar: unfamiliar is the point. Redraw a slot only when it conflicts
with a stated brand constraint or needs an asset that does not exist, and say why in your report.

The parts of this sheet were written separately and will disagree in small ways. Settle every disagreement in this order:
**house rules** (including type no smaller than 13px and body text of 16px or more) → **the direction** (the idea, the composition habits, where the
one accent goes) → **the type system and the palette** (which face does which job, the five size steps, which colour is the ground and where the
accent goes) → **the hero blueprint** → **the section blueprints**. Under each blueprint below, "Adjusted for this page" lists where it disagrees.
In practice: take geometry from blueprints (columns, proportions, what sits where) and take everything else from above them. Map every size a
blueprint names onto one of your five type steps instead of adding a sixth. Use one button shape, one corner radius and one pair of page margins on
the whole page, whatever individual blueprints say. If a blueprint names a kind of typeface (a light serif, a heavy grotesk), use the dealt face.

## 1. The idea
One short sentence, set at poster scale, is the composition. The trick that makes it an idea rather than a big headline: something from the subject sits inside the sentence where a word would be. A strip of photograph fills the gap between two words; a small live fragment of the product replaces the noun; the object the sentence names is pictured at the size of a letter. Write the sentence first, find the word that can be shown instead of said, and put the showing in its place. The reader completes the sentence with their eyes.

Before anything else, write one sentence in your notes: "On this page, <the subject's own material> becomes <the device>."
Fill the first blank from your inventory of what only this client has (its name and what it means, its street, its numbers, its
constraint), then put the nearest competitor in the sentence: if it still works, the idea is the category's, not the client's.
Then name the one live thing the visitor can do on the page (SKILL.md step 4).

## 2. Composition
The sentence is four to seven words and runs as one or two full-width lines at 9–13vw. Inline with the type, on the baseline, sits one media slot: a rounded-rectangle or square frame exactly one line-height tall and two to three ems wide, holding a photograph or a looping crop. Above and below the sentence the screen is empty except for a small navigation line and one supporting sentence set small, both on the same left margin. Later sections repeat the grammar at smaller scale: each is a short statement on the left six columns with its proof (image, figure, list) on the right, so the page reads as a series of sentences with evidence. Generous vertical space (160px or more) between sections.

## 3. Type — Big Shoulders / Public Sans
A tall American gothic taken from city signage, blunt and civic, over a plain public-service sans. Suits culture indexes, community projects, bars, sport clubs and local campaigns.
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@800&family=Public+Sans:wght@400;600&display=swap" rel="stylesheet">
```
- Display: **Big Shoulders** — weight 800 · tracking -0.005em · leading 0.88 · uppercase
- Text: **Public Sans** — 400 for body, 600 for emphasis · leading 1.5 · tracking 0
```css
:root {
  --step-small: clamp(0.8125rem, 0.79rem + 0.1vw, 0.875rem);
  --step-body: clamp(1.0625rem, 1rem + 0.25vw, 1.1875rem);
  --step-lead: clamp(1.25rem, 1.1rem + 0.7vw, 1.625rem);
  --step-head: clamp(2.5rem, 1.2rem + 5vw, 5.5rem);
}
```
Display weight with real presence (medium to bold), tracking -0.03 to -0.05em, leading 0.95–1.0 so two lines sit close. The inline frame aligns to cap height and baseline exactly; set it with em units so it scales with the type.
The direction decides sizes and how many of them; the type system decides how this face is set. Where the two give different tracking or leading, use the values of the type system: they are tuned to this face.
The display size itself comes from the hero blueprint below.

## 4. Colour — Tobacco and olive
```css
:root {
  --bg: #472913;
  --surface: #55321a;
  --ink: #e4e0cf;
  --muted: #b39f84;
  --accent: #525e1b;
  --accent-ink: #e4e0cf;
  --field-1: #c79a3e;  --field-1-ink: #2b170a;
  --field-2: #525e1b;  --field-2-ink: #e4e0cf;
}
```
Tobacco brown fills the page with bone type, and photographs stay in browns and ochre. One olive block holds the main text or the button, and a single ochre band may break the brown once.
A calm ground with ink at full contrast. The only colour comes from the photograph inside the sentence; if the palette has an accent, use it once, on the action.

## 5. Imagery
**The project has no photographs of its own yet.** First choice: **real pictures of the subject's world from the open collections**: its city and street in old postcards and photographs, an old map of the neighbourhood, its materials up close, its trade in engravings, museum objects of its kind (references/imagery.md §3). Start with `node D:/6_OJT/Academic-Phrase-Rhetorical-Knowledge-Base/.agents/skills/design-taste-frontend/scripts/assets.mjs "internal phrasebank"`, then queries from your inventory (its street, its materials, its trade's tools and history). Download what you use into the project with `--get` and credit every one on the page (`--credits` prints the footer line). They show the world around the client, never the client's own room, dish, product, person or team. Second, for what no honest picture exists of: draw the subject's own things in code, large, in one flat graphic language and the palette's real colours (its tiles, its windows, its objects; references/imagery.md §8). Third: the dealt photographs, only where an honestly generic picture fits (the sea, the weather, a material), never one a visitor could take for the thing itself and never an unrelated scene. One treatment for all of them. If this direction is built on photographs, plan the set before building (four to six pictures of one family) and reuse them at different crops and scales instead of finding or drawing a new picture for every slot; keep drawings as `<symbol>` + `<use>` or generate them with a small script so the page stays light. List every found picture (with its source and licence), every dealt photograph and every drawing that stands in for photography in your report.

One strong, simple photograph that reads at small size (a face, an object, a texture, a horizon), cropped to a wide strip inside the sentence. The same image may open to full width in the next section, so the small slot feels like a window onto something larger.

**Floor (the inspector checks it):** at least four real pictures on the page, usually six to twelve; SVG drawings do not count. One moving picture where an honest clip exists: `node <skill>/scripts/assets.mjs --video "<query>"`, used as a muted loop with a poster frame. Whatever this direction says about pictures, it is carried out with real ones.

Photographs dealt for this build, from the "People" set (figures, silhouettes and portraits, mostly unposed)
Order of preference for imagery: (1) the project's own photographs and product shots; (2) images you generate, if an image tool is
available; (3) real pictures of the subject's world found in the open collections (assets.mjs, downloaded and credited on the page);
(4) drawings of the subject in code; (5) these. They are real photographs (Unsplash licence, served by picsum.photos) of places, light and
texture. They are atmosphere, never a stand-in for a specific product, dish, person or interface. List the ones you use in your report so
they can be replaced.
- `https://picsum.photos/id/338/1600/1000` — Person in a hooded coat seen from behind facing a misty sea · mid tone · slate blue, grey, charcoal · calm area: left · native landscape · photo: Patryk Sobczak
- `https://picsum.photos/id/669/1600/1000` — Person in a mustard jacket and grey beanie seen from behind in fog · light tone · mustard, pale grey, white · calm area: left · native landscape · photo: Luke Pamer
- `https://picsum.photos/id/685/1600/1000` — Man sitting on a rock looking over a sea of clouds · mid tone · pale gold, grey, dark brown · calm area: right · native landscape · photo: Joshua Earle
- `https://picsum.photos/id/177/1600/1000` — Hiker with a backpack looking over a hazy mountain valley · mid tone · warm tan, hazy gold, olive · calm area: left · native landscape · photo: Danka & Peter
- `https://picsum.photos/id/660/1600/1000` — Woman in a knitted cardigan holding a lit sparkler in front of her · dark tone · dark teal, grey, warm white · calm area: left · native landscape · photo: Morgan Sessions
- `https://picsum.photos/id/550/1600/1000` — Woman seen from behind looking over a blurred city at dusk · mid tone · dusty pink, warm grey, dark brown · calm area: top · native portrait · photo: Christopher Sardegna
- `https://picsum.photos/id/349/1600/1000` — Man sitting on a sea wall looking toward a hazy skyline · mid tone · warm grey, sepia, charcoal · calm area: left · native landscape · photo: Caleb George
- `https://picsum.photos/id/446/1600/1000` — Swimmer diving underwater in deep blue water with rising bubbles · dark tone · deep blue, navy · calm area: top · native landscape · photo: Jacob Walti
The last two path numbers are width and height: request the exact crop you render (`/1200/1500` for a 4:5 portrait, `/2400/1350` for a hero) and
add `?grayscale` to desaturate. Use three to six of them, not all eight. Always set `width`, `height`, `alt` and `loading="lazy"` (not on the hero image).
Other sets that fit this brief: architecture, hands-and-making, mountain, city-day — `node draw.mjs --photos <set>` prints one in full; `--photos list` shows all sets. Taking photographs from another set is your call and is not a redraw; keep them to one light and one treatment.

## 6. Hero — Headline across two fields
The viewport is two flat fields meeting at exactly half height: paper above, one saturated colour below, with a hard edge and nothing drawn on it. A two-line headline in black-weight capitals at clamp(96px, 9.5vw, 150px), line-height 0.86, is centred across the seam and spans about 70% of the width, so line one stands on the upper field and line two is cut through its upper third by the seam. The type changes ink where it crosses: above the seam it takes the accent ink, below it a deep ink two steps darker than the lower field, as if submerged. Build it as two stacked copies of the same headline, one per ink, the first clipped with `clip-path: inset(0 0 50% 0)` and the second with `inset(50% 0 0 0)`. Wordmark top-left at 28px; up to four text links and the single action, a solid rectangular button, top-right. One supporting sentence at 20px in the paper colour is centred on the lower field, 56px above the bottom edge. The lower field continues for 30svh past the fold before the next colour begins.

On a phone: The same two fields with the seam at 46svh. The headline stays on two lines at 15vw, centred, still cut by the seam and still changing ink. Wordmark top-left and the action button top-right; the links drop into one menu word beside it. The supporting sentence sits on the lower field at 16px, centred, max 28ch, with 40px beneath it.
Headline: A statement of two to four words on two lines, up to about 10 characters per line, whose meaning the rising field acts out.

Adjusted for this page:
- It names a kind of typeface: use the dealt faces (display Big Shoulders, text Public Sans) and their settings; capitals only where the type system sets them.
- It names colours (black): map them onto this palette's roles (ground `--bg`, panels `--surface` and the fields, text `--ink`/`--muted`, the accent `--accent` on the primary action only).
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.

## 7. Sections, in order
Each is a composition to rebuild with this project's content. Keep the geometry; change the subject. Re-order or drop a
section when the argument of the page needs it (see references/copy.md), never to fall back to a card grid.

### 1. intro — Headline crossing onto a photograph (split)
A white or pale ground. A photograph taller than it is wide, 720px wide (columns 7–12), sits flush against the right viewport edge with its top at 46% of the section's first screen and runs below the fold. The heading starts on the 32px left margin across columns 1–8: two lines of light-weight serif capitals at clamp(64px, 5.6vw, 88px), leading 1.04, the first line starting 34% down the screen and the second placed so that its right half runs onto the photograph's upper-left corner. Choose a picture whose upper-left quarter is pale enough for the ink, or set the second line twice, in the ink and in the paper colour, each copy clipped to its side of the photograph's left edge. Under the heading on columns 1–5, one paragraph of up to 25 words at 22px, leading 1.4. At the bottom-left a second, smaller photograph of 360×400px enters, cropped by the screen's lower edge, and on the next screen becomes the left half of a staggered pair with the large one. Nothing else is on the screen.
On a phone: The heading sits at 10vw on two lines on the 20px margin. The photograph becomes 75% of the width, flush right, and starts under the heading's first line so the second line crosses its top-left corner. The paragraph follows at 17px, then the small photograph at 50% of the width on the left margin.

Adjusted for this page:
- It names a kind of typeface: use the dealt faces (display Big Shoulders, text Public Sans) and their settings; capitals only where the type system sets them.
- It names colours (white): map them onto this palette's roles (ground `--bg`, panels `--surface` and the fields, text `--ink`/`--muted`, the accent `--accent` on the primary action only).
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.
- It numbers things 01, 02: drop the numbers unless they are real data (a price, a date, a count).

### 2. showcase — Object in front of type (statement)
Type and object share one space instead of sitting side by side. Three or four lines of display type, one or two words each, are stacked flush left at clamp(72px, 9vw, 150px) with leading 0.88, starting on the left margin and allowed to leave the right edge (white-space: nowrap; overflow: hidden on the section). The lines step through tones of one ink: one at 45%, one at full strength, the rest at 18%. The object photograph, a cut-out or a studio shot blended with multiply, is absolutely positioned over the upper right of the stack at 40–46vw wide, rotated no more than 6 degrees and above the type in the stacking order, so it hides parts of three or four letters. Under the stack, in columns 8–12, a two-paragraph block at 20px gives the facts. The full-strength line is the heading; nothing sits above it.
On a phone: Type drops to 15vw and still runs off the right edge. The object sits at 78vw wide, overlapping the last two lines from below instead of from the right, and is cropped by the right edge. The facts block follows at full width and 17px.

Adjusted for this page:
- It fades text: anything a visitor reads, inactive items of a list included, is `--ink` or `--muted` at full strength (contrast 4.5:1 or more). The active item is told apart by `--ink` against `--muted`, weight or the accent, not by fading the rest.
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.

### 3. how-it-works — One verb at a time (full-bleed)
Three to five full-bleed panels, each 100svh tall, stacked with no gap; each is one stage and holds one photograph covering it. In every panel a single word, the verb for that stage ('Cut', 'Fold', 'Stitch', 'Press'), is set at clamp(96px, 17vw, 300px), heavy and centred, inside a wrapper that is position: sticky; top: 50% and shifted up by half its own height. Because each word is sticky only within its own panel, it holds the centre of the screen while its photograph passes behind it, and is then pushed out by the next panel's verb. Use mix-blend-mode: difference in white, or one solid colour tested on every image. One sentence at 18px sits in the bottom-left corner of each panel over a neutral scrim limited to that corner. There is no separate heading: the verbs, read in order, are both the heading and the sequence.
On a phone: Panels stay 100svh, each photograph cropped to a vertical slice. The verb is 24vw, still sticky at the centre. The sentence sits along the bottom over a scrim at 16px, full width with 16px margins.

Adjusted for this page:
- It names colours (white): map them onto this palette's roles (ground `--bg`, panels `--surface` and the fields, text `--ink`/`--muted`, the accent `--accent` on the primary action only).
- It blends text with `difference`: over anything but black, white or grey that gives random hues. Use a solid ink chosen for each ground instead.
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.

### 4. list — Statement, table pushed right (table)
A heading of four to six words spans the full width on two lines at clamp(40px, 4.5vw, 68px), left-aligned with its first line indented 3vw and leading 0.98. 96px below, the table is pushed into the right-hand five columns (8–12) and the left stays open. One plain word naming the table (offices, hours, rates) hangs at 14px in column 7, top-aligned with the first row. Each row is a three-part line at 15–16px with 26px between rows: the kind or day in the soft ink at the left of the measure, the place or service at 30%, and the address, time or price right-aligned, with a small arrow where the row links. Rows are separated by space only; every fourth row has 44px above it to form groups. In columns 1–4, bottom-aligned with the last row, one 4:5 photograph 22vw wide may sit alone. Holds 5–14 rows.
On a phone: Heading at 9.5vw without the indent. The table takes the full width at 16px; each row stacks the kind above the place, with the value right-aligned on the first line. The naming word is dropped because the heading already says it. The photograph follows at 60% width on the right margin.

Adjusted for this page:
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.

### 5. faq — Wide heading, indented questions (list)
A heading of three to five words at about 5.5vw runs from the left margin on one or two lines and is the only large thing in the section. 80px beneath it the questions begin, indented to start at column 5 and running to column 12, so the left third under the heading stays empty. Each question is a row at 22–24px in the regular weight with a chevron of two 2px strokes at the far right; rows are separated by 36px of space and no rules. Opening a row lays a tile of the one-step tone behind that row and its answer (24px padding, extending 24px beyond the text on both sides) and shows the answer at 17px with a 48ch measure. Six questions. Nothing else shares the screen; the indent against the wide heading is the composition. Build with `<details>`.
On a phone: The heading sits at 10vw on two lines. Questions lose the indent and run full width at 19px with 28px between rows; the open row keeps its tone tile, now bleeding to both screen edges, with the answer at 16px inside it.

Adjusted for this page:
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.

### 6. cta — Question at both edges (statement)
For a closing choice between two answers: book or ask, this date or that, the tasting or the tour. A flat field exactly 100svh tall in the darkest tone. The question is a two-line heading at clamp(110px, 11vw, 168px), leading 1.0, centred, about 54% of the width: line one with its cap line 32px under the field's top edge, line two with its baseline 24px above the bottom edge. The band of about 560px between them is empty except for one row at its optical centre: two solid rectangular buttons, each about 200×56px with its label at 18px in medium weight, their inner edges 120px either side of the centre axis, and between them, exactly on the axis, the word 'or' at 18px in the soft ink. 16px under the row, centred, one line at 16px in the soft ink says what happens after either choice. The type above and below closes the empty band, so it reads as held breath rather than a gap.
On a phone: The question drops to 18vw, still two centred lines, line one 32px from the top and line two 24px above the bottom. The buttons stack at the centre at 72% of the width, 12px apart, with 'or' between them and the line of explanation under the second.

Adjusted for this page:
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.

### 7. footer — Invitation over a cropped name (statement)
Close and footer in one full-viewport field of the inverse colour. Upper third, columns 1–7: a two-line invitation at about 5vw, three to five words, with one filled rectangular button beneath it. At columns 10–12, top-aligned with the invitation, three or four social or contact links stacked at 16px. The wordmark fills the bottom of the screen at 26–30vw on one line, `white-space: nowrap`, heavier and larger than the viewport can hold: it is pushed down with `transform: translateY(30%)` so the bottom edge cuts through the letters, and a long name also runs off the right edge. `overflow: hidden` on the footer does the cropping. One row of credits and legal links at 13px sits directly above the wordmark's cap line, spread left and right. The cropped name must be recognisable from its upper two-thirds alone; test that it is.
On a phone: Invitation at 11vw on two lines at the top with a full-width button. Links follow as one row of words at 15px. The wordmark sits at 34vw at the bottom, cropped by both the bottom and the right edge, with the legal row above it at 12px.

Adjusted for this page:
- It sets text at 12px: use your small step (13px or more) instead.
- Its vw sizes assume a face of normal width: with this condensed display face, size the words to fill the measure the blueprint gives them instead of copying the vw value.

## 8. Motion — Colour by chapter
Each chapter is its own full-bleed field of one palette colour, so the ground changes exactly at section edges as you scroll, never as a global recolouring of the screen. The only movement: the fixed header (or the one pinned element) takes the ink of the chapter beneath it, switching with a 300ms colour transition as each edge passes under it. Do not drive the page background from an observer: in blind tests a page recoloured mid-section, with a paragraph sitting on two colours, read as broken twice.
This is the signature move, the one loud moment. Around it the page still needs the rest of the motion layer (SKILL.md step 9): an entrance for the parts of every section, feedback on every control, and one moving picture. The inspector fails a page that barely moves. Recipes: references/motion.md.

## 10. Where the richness comes from
The collision of big type and one live image inside it. Because there is only one image on the first screen, choose it with care and give it perfect alignment to the letters.

## 11. How this direction goes wrong
The sentence must be short enough for two lines on a phone, where the inline frame drops to its own line between the two halves. Do not style one word differently to fake the device. Do not use more than one slot per sentence.

## 12. Real references
Studied sites that work this way. Take the principle, never the specifics: no names, copy, images or signature assets of theirs.
- **bleibtgleich’26** (Awwwards Site of the Day, studied score 7.5) `aww-bleibtgleich26`
  Idea: One thin vertical rule runs down the page and a tight bold grotesk sentence wraps around it, words stepping from one side of the line to the other.
  Hero: White page, black type. Content sits in a narrow band between 26% and 68% of the width. A 1px vertical rule drops from the top edge at 37% for two-thirds of the height. Left of it: a black blob avatar at the top, a tiny role caption at its foot. Right of it: a tiny location note at the top, the name in two lines of 90px medium grotesk at the bottom. The tagline continues below at the same size, flush to the band's left edge, running past the fold. The upper half is otherwise blank. The handle is split into two pale-grey words fixed in the bottom corners; a black menu pill sits top-right.
  Worth taking: Draw one 1px vertical rule and typeset a large sentence around it, alternating words to either side so the line becomes the text's spine.
- **CoffeeTech®** (Awwwards Site of the Day, studied score 7.1) `aww-coffeetech-r`
  Idea: Present an industrial roaster maker like a design brand: one enormous three-word statement on black, with the machine withheld until the first scroll, where it emerges from the dark.
  Hero: Near-black viewport with nothing but type. A centred three-line headline, one word per line, in Inter Medium at about 15vw with tight tracking; the first line starts a third of the way down and the last runs to within 35px of the bottom edge, its widest word spanning roughly 70% of the width. Cream letters; no subhead, no media, no hero button. Navigation is one quiet row: logo with a terracotta mark at left, four text links centred, then a filled terracotta 'Products' button with a grid icon, an outlined contact button and a language dropdown at right. The top third stays empty.
  Worth taking: Let a three-word headline at about 15vw be the entire first viewport and withhold the product until the first scroll.
Full notes on any of them: `node draw.mjs --site <id>`.

## Always
Headlines two lines or fewer at every width. No eyebrow labels, no monospace, no 01/02/03, no thin rules, no gradients, no shadows at rest,
no cream-and-terracotta, no violet. The frame: one h1 on the first screen that says what this is, equal outer margins, no
section huddled on one side with the other half empty, no blank stretch over half a screen, a heading on every section.
`inspect.mjs` measures all of it.

Saved to C:/Users/QUOCTH~1/AppData/Local/Temp/claude/d--6-OJT-Academic-Phrase-Rhetorical-Knowledge-Base/cab1a22b-4665-4562-84ab-f864ecd4cf1f/scratchpad/taste/direction.json · reprint with `node draw.mjs --show`
