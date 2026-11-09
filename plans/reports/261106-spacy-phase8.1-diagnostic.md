# Phase 8.1 diagnostic — Construction Matcher correctness recovery

Date: 2026-11-06  
Worktree: `D:\6_OJT\aprkb-spacy-spike`  
Branch / base: `feat/spacy-nlp-spike` / `184bc0203f4d66b1d487354245df63adcd135ace`

## Working-tree boundary

The pre-existing Phase 8/9.1 edits and untracked reports were present before this diagnostic.
The files `apps/backend/src/aprkb/policies/gold_labeling.yaml`,
`eval/mining/gold/ANNOTATION_STATUS.md`, and `eval/mining/gold/GUIDELINE.md` were already modified
and are protected. They were left untouched. No matcher behavior was changed before this report.

## Scope and counts

Counts-only analysis used the same 51 allowed stored articles and spaCy 3.8.18 token features.
The sample has 708 kept sentences with subject `we` and one of the 11 registered anchors. Current
matcher outcomes are 45 matches, 369 `unlisted_adjunct`, 128 `missing_child`, 87
`coordinated_construction`, 66 `unsafe_frame`, 10 `too_many_adjuncts`, and 3
`unsupported_subject`. No source sentence or masked frame was emitted.

## Findings

### Object-internal prepositions

The failure is localized in `_match_rule`: it collects every `prep` descendant of the direct
object into `object_prep_nodes`, merges them with predicate children, then validates all of them
against the construction adjunct list. In this sample, 290 unlisted-preposition occurrences were
counted: 221 attached within the object subtree and 69 attached to the predicate. The current code
therefore applies the predicate adjunct allowlist to a majority of object-internal PPs.

The object span helper compounds this: `_noun_content_span` removes every preposition subtree from
the object and rejects when removed tokens intersect the resulting source-span envelope. Of 128
`missing_child` outcomes in this `we` + anchor slice, 58 were exactly this invalid/interleaved
object-content-span path. The other 70 had no resolved direct-object (`X`) path. Among those 70,
63 had a direct `xcomp` (17), `advcl` (25), `ccomp` (20), or `oprd` (1) dependent instead; the
remaining seven had other dependency shapes. These are structural categories, not proof that every
sentence can safely be converted to an object slot.

### `unsafe_frame`

The 66 rejections were separately profiled. The following features overlap and are not mutually
exclusive: 54 had content before the subject, 52 contained a comma, 18 contained parentheses, one
contained a bracket/citation, one contained quotation marks, and one contained a semicolon or
colon. Eight had more than six words after removing slot markers; 58 had six or fewer.

The policy validator only accepts its declared subject/anchor/slot grammar and a narrow optional
`in this ...` prefix. This explains why source-preserving frames with other surrounding content can
fail validation, but the character profile does not establish a single cause for every row. Phase
8.1 must preserve closed-world rejection for genuinely unsupported content while identifying the
specific invalid boundary or grammar condition; the grammar must not be broadened from counts alone.

### Modifier and auxiliary candidates

Among rejected `we` + anchor cases, the root's direct dependents included 74 occurrences from the
candidate modifier list: `also` 17, `first` 13, `then` 10, `here` 9, `therefore` 8,
`additionally` 6, `finally` 6, `next` 5. The same profile had 15 auxiliary occurrences:
`have` 10 and `will` 5. These are token occurrences, not deduplicated sentence counts. Other
observed dependents included `and` coordination, `far`, citation-like bracket tokens, and parser
metadata artifacts; this confirms that the candidate lists are not blanket permissions.

The matcher currently allows only `aux`, `auxpass`, `neg`, and `advmod` as the anchor's verb group,
but then rejects most of these tokens at the generic literal-content check because they are not in
`allowed_literal`. The `have`/`will` candidates are structurally labeled `aux` in the counted
examples; main-verb uses must still be excluded by dependency role in the implementation.

## Implementation implications

1. Compute the `X` source span from the complete object subtree, retaining its nested PPs.
2. Classify only structurally predicate-level PPs as construction adjuncts; keep object-internal
   PPs in `X` regardless of their preposition lemma.
3. Preserve the current closed predicate-level adjunct inventory and reject unsupported predicate
   adjuncts.
4. Add independent closed modifier and auxiliary lists, then require the expected dependency and
   position for each token.
5. Split `missing_child` only into evidence-backed failures (missing subject, missing object, or
   invalid source span). Diagnose unsafe-frame failures from span/boundary checks; do not relabel
   all 66 uniformly.
6. Use deterministic counts and anonymous hashes for the mandatory 42-instance comparison. The
   original 42 Phase 7 cases are mandatory compatibility targets under this phase's owner decision.

The 42-instance baseline currently records 1 unchanged, 14 changed, and 27 rejected in the Phase 8
report. This is a known failure against the Phase 8.1 acceptance criterion and must be recomputed
after implementation. The prior Phase 9.1 report also used the wrong base identifier and its
integration result must be corrected after the required verified-container test run.
