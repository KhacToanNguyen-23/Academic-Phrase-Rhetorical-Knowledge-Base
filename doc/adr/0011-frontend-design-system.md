# ADR-0011: Frontend design system

Status: Accepted for the internal tool.

## Context

The web app had a hand-written stylesheet (`styles.css`), home-made UI primitives and a staff-only front door. The owner asked for a redesign that is minimal, geometric and still academic, with a public landing page and shadcn components for controls. The full plan is in `plans/ui-redesign/`.

## Decision

- **Stack.** Tailwind v4 (`@tailwindcss/vite`) with shadcn/ui on Radix. Components live in `apps/web/src/components/ui`, product components in `apps/web/src/components/domain`. Sans is Be Vietnam Pro, serif (phrases, headwords) is Newsreader. Switzer was dropped after a glyph check found it lacks 46 of 52 Vietnamese letters.
- **Two directions from the taste skill.** The landing uses `sentence-as-layout` (seed 568972173). The app uses `achromatic-ledger` (seed 436108652) with an open-plane shell. Priority when rules disagree: owner decisions, then `CLAUDE.md`, then the taste skill, then shadcn rules, then frontend-mindset.
- **Colour.** One brand colour, SLRS teal `#176b8f`, used sparingly: at most one primary button per screen, the active navigation item, and phrase slots. Never on tabs, cards, headers or large areas. Everything else is neutral. Error red is separate from teal so it is never mistaken for a slot.
- **Routes.** `/` is a public landing page, `/signin` is its own page, `/app` is the staff workspace. All other paths are unchanged and sit under a guarded layout (`beforeLoad`) that redirects to `/signin?next=...`; `next` accepts only same-origin relative paths. `/writer` stays open to guests.
- **Language.** The landing is English by default. Every landing string lives in `features/landing/copy.en.ts`, typed as `LandingCopy`, so a Vietnamese file can be added later without touching markup.
- **Devices.** Desktop web only (1440px, minimum 1024px). No mobile or tablet work.
- **Testing.** Playwright is switched off for this redesign. Screens are checked with the taste skill's `inspect.mjs` and with Browser MCP or CDP scripts. The e2e specs under `apps/web/e2e/` were not updated and are expected to fail until the owner decides to rewrite or remove them.
- **Package manager.** pnpm only, because CI installs with `pnpm install --frozen-lockfile`. `package-lock.json` was removed.
- **Build modes.** A separate `inspect` build mode auto-signs in through the loopback-only demo session so staff screens can be measured. The `/dev/ui` inventory page and the demo session exist only in development and in that mode; the production build contains neither.

## Deviations from the taste skill (recorded on purpose)

- Teal is used for the primary action, the active navigation item and slots, where `achromatic-ledger` would use none.
- The landing's headline slot uses the phrase face (Newsreader) inside a sans headline. It is the product's own live specimen.
- Pictures on the landing are archival engravings and one clip, all with a commercial licence and credited in the footer. They illustrate the world around the product, not the product itself. The owner decided not to use screenshots of the app on the landing page.

## Consequences

- Legacy `styles.css` and `shared/ui` are removed; new screens must use `components/ui` and `components/domain`.
- Several screens still read mock data (`shared/api/mock-*.ts`). The redesign did not change data sources.
- The admin key dialog and Gold/Extract with real data were verified only with a curator demo session; they need a run with an admin key.
