# ADR-0011: Frontend design system

Status: Accepted for the internal tool.

## Context

The web app had a hand-written stylesheet (`styles.css`), home-made UI primitives and a staff-only front door. The owner first asked for a redesign that is minimal, geometric and still academic, and later (2026-11-04) refined the direction to a Refined Editorial Workspace, with a public landing page and shadcn components for controls. The full plan is in `plans/ui-redesign/`.

## Decision

- **Direction.** Refined Editorial Workspace: an academic editorial aesthetic with a modern research tool. It replaces the earlier "minimal and geometric" direction as the primary one (2026-11-04). The product should feel like a carefully designed academic reference workspace, not a generic SaaS dashboard and not a rigid neo-brutalist interface. Layout stays precise and aligned; typography, whitespace and hierarchy organise content before borders or cards; surfaces and borders are restrained; nested cards are avoided; pills are for badges, tags and compact status only; the landing page is styled apart from the signed-in workspace. Details are in `plans/ui-redesign/plan.md`.
- **Radius scale (owner-approved).** Panels (card, dialog, popover, menu container) 8px; controls (button, input, textarea, select trigger, toggle) 6px; menu, select and command items and tooltips 4px; badges are pills; slots 2px; tabs are underline with no radius; table rows are not rounded. Landing buttons, images and fields stay 0px; only the hero's UI preview frame uses 8px. Tokens: `--radius-panel`, `--radius-control`, `--radius-item`, `--radius-pill`, `--radius-chip` in `globals.css`.
- **Phasing.** The radius scale was applied at the `components/ui` and token level only. Removing nested cards and unnecessary borders screen by screen, and a separate surface and border token set for dark mode, are Phase 08, delivered in waves like Phase 05. Phase 08 has not started.
- **Stack.** Tailwind v4 (`@tailwindcss/vite`) with shadcn/ui on Radix. Components live in `apps/web/src/components/ui`, product components in `apps/web/src/components/domain`. Sans is Be Vietnam Pro, serif (phrases, headwords) is Newsreader. Switzer was dropped after a glyph check found it lacks 46 of 52 Vietnamese letters.
- **Two starting points from the taste skill.** The landing uses `sentence-as-layout` (seed 568972173). The app started from `achromatic-ledger` (seed 436108652) with an open-plane shell and now follows the Refined Editorial Workspace direction above. Priority when rules disagree: owner decisions, then `CLAUDE.md`, then the taste skill, then shadcn rules, then frontend-mindset.
- **Colour.** One brand colour, SLRS teal `#176b8f`, used sparingly: at most one primary button per screen, the active navigation item, and phrase slots. Never on tabs, cards, headers or large areas. Everything else is neutral. Error red is separate from teal so it is never mistaken for a slot.
- **Routes.** `/` is a public landing page, `/signin` is its own page, `/app` is the staff workspace. All other paths are unchanged and sit under a guarded layout (`beforeLoad`) that redirects to `/signin?next=...`; `next` accepts only same-origin relative paths. `/writer` stays open to guests.
- **Language.** The landing is English by default. Every landing string lives in `features/landing/copy.en.ts`, typed as `LandingCopy`, so a Vietnamese file can be added later without touching markup.
- **Devices.** Desktop web only (1440px, minimum 1024px). No mobile or tablet work.
- **Testing.** Screens are checked with the taste skill's `inspect.mjs` and with Browser MCP or CDP scripts. On 2026-11-06, in response to CI failures, the Phrasebank and live Writer e2e specs were updated for the redesigned controls and markup while retaining behavioral coverage. Playwright runs as the existing Stage A CI smoke, not a required check; this does not replace visual design inspection.
- **Package manager.** pnpm only, because CI installs with `pnpm install --frozen-lockfile`. `package-lock.json` was removed.
- **Build modes.** A separate `inspect` build mode auto-signs in through the loopback-only demo session so staff screens can be measured. The `/dev/ui` inventory page and the demo session exist only in development and in that mode; the production build contains neither.

## Deviations from the taste skill (recorded on purpose)

- **Radius and borders.** The taste skill asks for one radius across a product and for as few borders as possible. This design uses a three-step radius scale (panel 8, control 6, item 4) so panels, controls and menu items keep a visible hierarchy, and keeps subtle one-pixel borders on inputs and tables. The owner approved this on 2026-11-04. A surface carries a border or a tone step, not both.
- Teal is used for the primary action, the active navigation item and slots, where `achromatic-ledger` would use none.
- The landing's headline slot uses the phrase face (Newsreader) inside a sans headline. It is the product's own live specimen.
- Pictures on the landing are archival engravings and one clip, all with a commercial licence and credited in the footer. They illustrate the world around the product, not the product itself. The owner decided not to use screenshots of the app on the landing page.

## Consequences

- Legacy `styles.css` and `shared/ui` are removed; new screens must use `components/ui` and `components/domain`.
- Several screens still read mock data (`shared/api/mock-*.ts`). The redesign did not change data sources.
- The admin key dialog and Gold/Extract with real data were verified only with a curator demo session; they need a run with an admin key.
