# Phase 07 polish: report (first round)

Scores are my own, using the critique scale (design 40, usability 30, creativity 20, content 10), from the 1440px screenshots. Treat them as relative, not as a jury score. Screens that need an admin key (Gold, Extract, Admin with data) could not be judged with data and were not scored.

## Before and after

| Screen | Before | After | What changed |
|---|---|---|---|
| Workspace `/app` | 5.8 | 7.0 | Figures now carry context ("oldest 5 days ago", "of 9 in the bank"). New "Needs attention" list (what an editor can act on, quarantined and in-review counts), a "The bank" panel with neutral bar charts (patterns by status, approved patterns by section), and a request table with latency and relative time. The empty lower half is gone. |
| Vocabulary | 6.5 | 7.2 | Summary strip (lemmas, core lemmas with share, word families). The letter index doubles as a bar chart of lemmas per letter. |
| Vocabulary detail | 6.4 | 7.0 | Seven metric cards became one figure strip. The discipline bars are neutral (they were teal, against the teal budget). The empty-distribution block is one line. The redundant "Inspect" column is gone. |
| Library | 6.9 | 7.1 | List summary shows counts by status. Slots and Usage contract are stacked, so guidance text no longer wraps one word per line. |
| Journals | 4.9 | 6.6 | The empty "Select a journal" panel is now a comparison table (verified rules, required rules, corpus articles, evidence status) with a link into each profile. |
| Phrasebank | 5.0 | 6.0 | When the Manchester reference is off, two "unavailable" cards collapse into one note and the bank's own patterns come first. |
| Inbox | 6.6 | 6.9 | A toast confirms every decision. Before, the confirmation lived in a panel that unmounted when the item left the queue. |
| Sign-in | 6.0 | 6.3 | One added sentence on where a key comes from. |

Top remaining problems: (1) Journals and Library still leave a tall empty area under short content; (2) most numbers are sourced from mock data on Library, Journals and Workspace, so they look plausible but are not live; (3) the Workspace needs Gold and Extract counts, which have no cheap endpoint.

## Gates

- `pnpm typecheck`, `pnpm lint`, `pnpm build`: pass (one old lint warning). No `dev/ui` or `demo-session` in `dist/`.
- `lint.mjs --app` on features, domain components and app: 0 FAIL.
- `inspect.mjs --app --widths 1440`: Workspace 0/0, Vocabulary 0/0, Vocabulary detail 0/0, Library 0/2, Journals 0/1, Phrasebank 0/1, Inbox 0/2 (FAIL/WARN).
- Teal budget script on 12 staff screens: at most one primary button per screen.
- No new dependency, no new API, no route change. Charts are plain `div` bars.

## Not done from the Phase 07 plan

- Gold and Extract queue progress and `kbd` hints (needs data that only an admin key shows).
- Import and Admin: job steps as readable text and a log filter.
- Writer and Playground: context summary near the result, copy button on JSON.
- A second look at Library's empty area and a before/after for screens not listed above.
