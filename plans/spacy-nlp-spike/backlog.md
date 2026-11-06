# Phase 9.1 backlog

## Corpus lead-ins awaiting owner review

These are counts only and were not added to `lead_ins.yaml`: then 2, empirically 2, in this
section 2, from the figure 2, together 2, in fact 2, additionally 2, plus 30 free-text lead-ins
longer than four words; the rest were singletons.

## Phase 9.1 completed

- Active literal subjects `this paper`, `this study`, and `this article` are accepted for the
  existing `author_action` anchors. Subject text stays literal; the X slot and Phase 8 adjunct
  registry are unchanged.
- `this method`, `this result`, `this approach`, other unlisted subjects, and passive subjects
  reject with `unsupported_subject` or `unsupported_voice`.

## Construction shapes still unsupported

- Passive voice.
- `it` subjects.
- Copula `be`.
- `this ...` subjects outside the exact Phase 9.1 list.
- Adjunct dependency types, prepositions and structures absent from the Phase 8 closed registry.

Proposed additions require owner review under FR-06.2. Do not grow runtime lists from mining data.
