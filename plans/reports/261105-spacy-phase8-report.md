# Slot abstractor phase 8 report

## Changes

- Bumped `constructions.yaml` to 0.2.0, added the provisional Tier-1 `author_action` anchors,
  and defined closed preposition/purpose adjunct lists with a two-slot limit and the literal
  `in this ...` exception. Each provisional list carries `TODO(owner, FR-06.2)`.
- `ConstructionMatcher` now keeps allowed prepositions and `to` literal, adds their objects or
  verb phrases as slots in surface order, handles actual object-attached preposition dependencies,
  and replaces only exact source spans. Unsupported dependencies and prepositions reject as
  `unlisted_adjunct`; a third adjunct rejects as `too_many_adjuncts`. Coordination behavior and
  reporting-first precedence remain in place.
- Added dynamic safe-frame validation derived from anchor lemmas. Other construction rules retain
  template validation. No database, persistence, API, lead-in, epistemic or V02 change was made.
- Added 19 self-authored token snapshots. The 85 prior snapshot cases are byte-content identical.
  The purpose test checks both `xcomp` and an `advcl` dependency variant on the same generated
  self-authored snapshot; the available spaCy 3.8.18 parse labels that bare infinitive `xcomp`.

## Counts-only corpus comparison

Analysis used the same 51 rights-checked stored articles and the same filtering/pipeline method as
phase 7. The corpus covers one field (federated learning). It contains one exact duplicate
(FedQueue, two copies) and one partial duplicate (two versions of a survey); these inflate
per-article counts. Figures below are this implementation's analysis, not an independent benchmark.
No sentence or frame text is included. Frame IDs below are SHA-256 prefixes.

| Measure | Before phase 8 (phase 7) | After phase 8 |
|---|---:|---:|
| Reporting extractions | 203 | 203 |
| Construction extractions | 43 | 46 |
| `author_action` | 42 | 45 |
| `performance` | 1 | 1 |
| Distinct masked frames | 70 | 102 |
| Distinct cluster keys | 207 | 239 |
| Frames with document frequency >= 2 | 35 | 35 |
| Construction `unmatched_content` | 211 | 49 |
| `unlisted_adjunct` | 0 | 372 |
| `too_many_adjuncts` | 0 | 10 |

New-anchor extractions: use 9, compare 1, conduct 4, evaluate 2, provide 4, consider 4,
implement 0. Other `author_action` counts after the change were introduce 3, present 11, propose 7;
develop had no match.

Top recurring after-phase-8 frames, identified only by hash and article document frequency:

| Frame ID | Document frequency |
|---|---:|
| `94d0ceb20a3b` | 17 |
| `d8585ebaee98` | 10 |
| `5f513d62767b` | 8 |
| `47c321ab0511` | 7 |
| `5bf74834d036` | 6 |
| `b838b33b2e43` | 5 |
| `594ea6613bc5` | 5 |
| `47dab89a8ecf` | 5 |
| `80e7f21a0ef6` | 5 |
| `b7f8370ddb44` | 4 |

Construction rejection comparison (phase 7 -> phase 8): `no_anchor` 11,250 -> 10,139;
`missing_child` 377 -> 1,054; `coordinated_construction` 93 -> 239; `unsafe_frame` 1 -> 66;
`unmatched_content` 211 -> 49; new `unlisted_adjunct` 0 -> 372; new `too_many_adjuncts` 0 -> 10.
The increased `missing_child` and `unsafe_frame` counts are included for owner review; unsupported
structures remain closed-world rejections.

### Phase 7 regression evidence for 42 author-action instances

The 42 Phase 7 extraction instances are compared below without source or frame text. Each
source identity hash is SHA-256 over the blob identity, sentence ordinal, and source offset;
output hashes are SHA-256 over the respective masked frames. Rejected Phase 8 outputs have no
output hash. A status of `changed` is accepted when the new frame obeys the whole-sentence
contract; the hash table makes each outcome and rejection reason traceable.

| Source identity hash | Phase 7 output hash | Phase 8 output hash | Status | Rejection reason |
|---|---|---|---|---|
| `284b89cbe5177e2eae951c470520487bab7a090d7a98e2341aee723e267d8786` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | `43de5f2705ab5996a50e75c8265d500f2e05c5536c45653c9793ef22af848e4e` | `changed` | — |
| `2c378430fc439c017e08d0425d23a51fb707b0d0c7cb17b4d79341f5961cdacd` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | — | `rejected` | `missing_child` |
| `2f1fbda44375aadb2b9f64197803075e7aa24396ee7670abe76e63efe8f66abc` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | — | `rejected` | `missing_child` |
| `2ffefe35092e6a6bea84ef28f5a7c4b7c867a29ec97342812920aebf3c449847` | `656cd3544a5dc058b031e94324e1f26d4e8b7c966c76087f5c257dfb1adfa355` | — | `rejected` | `missing_child` |
| `3365823118192d38fc425a98cad1bee92a3ca62ab1e653ae0ce26767c2e9b96c` | `0ed82aec8812946b63ba6418953c535454add24c9a44394dc060a20e6a7c4676` | `0ed82aec8812946b63ba6418953c535454add24c9a44394dc060a20e6a7c4676` | `unchanged` | — |
| `37cfa804406a52534640f6c108ec001abf0a8cdb016648cf2a6ec5da90a0d5ea` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | — | `rejected` | `unlisted_adjunct` |
| `39f0de2e42f06cf7525ac171d025c67571de9432f64769cdc5096a9d4e480310` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | `0cd716f91ca629a773f22a346537878c6b910eaa971c4791b14e90d88fad1299` | `changed` | — |
| `3f1da492bba428f2ba0a6720fda01a11062eaae2d43f82332fb5477ec0506891` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `unlisted_adjunct` |
| `3f41ef12beed1e9cbbb85ad477ebce15250cf596614d55404d38092d93f67d08` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `unlisted_adjunct` |
| `43c74b2d2769623dad8ce614ca4c61e2e3d51a68ba99b8b2f1b08506694dbe13` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | `f494eae226dfbd7d26a813800b88ba185b9b2af765b655f13f229960ed7abb14` | `changed` | — |
| `43f73157333f639c9498d7f8b7b857eb5b17ed6516ae3d3965a436a8cb46aa73` | `0ed82aec8812946b63ba6418953c535454add24c9a44394dc060a20e6a7c4676` | `d02193733d8231e2dd1a33bfa12222ba26ac637423271c25dfe52af96bfc4793` | `changed` | — |
| `4c9afaef3a3827e3524a064b3a1a82dfa4b6748df20f75de83fab4810d8468bc` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `unlisted_adjunct` |
| `5097823388a01f4465dd34a3da8515c9013009cb1b9e851dab3ce32bd00dda62` | `2ac9074c82540d36c7a2b3277e28f02c5d7e067917a23dbb6da0000f0ec542d4` | `544531375c32ca91afc0e5447ca4e169e256847c43d2f5ac7b8e48f5564ed469` | `changed` | — |
| `5a56d2b3e8557ec9712c8ab1d88bc1034fd7c8ee1b8e660301665bae06a78f79` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `unlisted_adjunct` |
| `63a7f2c81a38356d6075ac3337a97f6c826fd9665a9fdfb38d3058c12a2995e0` | `696bfbcb9ab53c1b209ec2ba93e21d6df93abb6fb5e93bffd2585334a6a0f3f0` | — | `rejected` | `unlisted_adjunct` |
| `68052fdcd855318e075b88b43e81e5f8823c4394d5e674be72b41d41b3a25484` | `68488e98367394dd660142d39e1ee685dd5ce961ec86657fba771d9ab00d77e8` | — | `rejected` | `missing_child` |
| `68bfa31eb7f8aef27efae4d4dd42ca6edb357a74cdf143ae65990093c4a03c96` | `68488e98367394dd660142d39e1ee685dd5ce961ec86657fba771d9ab00d77e8` | `d608cea7df6c25fb0293c59a79ae09ba7b97758a939a381dab417af19e10cb5f` | `changed` | — |
| `70d1a72f2000bdf8e7d564c0d5c841fdf10fdd77f73739d67b00840e9391be2c` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | `f494eae226dfbd7d26a813800b88ba185b9b2af765b655f13f229960ed7abb14` | `changed` | — |
| `788279440cd723b02ea3e2af9c0d40a892db656df1d880f544b007dac45450c4` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `missing_child` |
| `7b3e11979d055b4e9238cc7722dffb9b9014de1fd474c88fc76184b001d11252` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `unsafe_frame` |
| `81d0b7de29ad551d9d23a99d0bde859ff488725736370da081367b6f91364d1a` | `68488e98367394dd660142d39e1ee685dd5ce961ec86657fba771d9ab00d77e8` | — | `rejected` | `unlisted_adjunct` |
| `85a40fe1891a7c95207579a9b1a04231f2bb681db6d23120b25371d3441007a1` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | — | `rejected` | `unlisted_adjunct` |
| `8a8ce2bad3d7431d54b63b5213283fb2829dd8254ea4b93102af7670f42e619e` | `0ed82aec8812946b63ba6418953c535454add24c9a44394dc060a20e6a7c4676` | `72df015034eda9fa00d132b02de54cbfd27c0852bdebcff263ee81c8314cbfed` | `changed` | — |
| `8ae4955e7aafd77349cf35f402f11de837ac59398cacad4c2352ca508d4b8d4f` | `2ac9074c82540d36c7a2b3277e28f02c5d7e067917a23dbb6da0000f0ec542d4` | — | `rejected` | `unlisted_adjunct` |
| `9857e57a180a2f82cf555ebe8480ee0f71aeefbae1b07d8cd8d9368c78487141` | `656cd3544a5dc058b031e94324e1f26d4e8b7c966c76087f5c257dfb1adfa355` | — | `rejected` | `unlisted_adjunct` |
| `b045344bddb6821a41f1bd269af32e3e467435a08c45fe29a072242e82605b87` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `unlisted_adjunct` |
| `b0f61544bd1af7d47b1103af1f553a2cf58daab8174dd01f1964be1493d39ee1` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | — | `rejected` | `unlisted_adjunct` |
| `b6febf743ae1f9eeb77f53de45570440aa64c2227457d035e73bf098f63bfb8a` | `0ed82aec8812946b63ba6418953c535454add24c9a44394dc060a20e6a7c4676` | `d02193733d8231e2dd1a33bfa12222ba26ac637423271c25dfe52af96bfc4793` | `changed` | — |
| `c2800731e17d8f4f000a076e4c3664fbad5db479027364d2cdaccb37bd6be24e` | `37720dbc96782ad1f14d04a43b594dee308a0f0f98480100780cfdba0568ac0f` | — | `rejected` | `missing_child` |
| `c8a94baafada8d3d3db48139489804a6fcbe453a757579c0865f7d5b5a21cbdc` | `656cd3544a5dc058b031e94324e1f26d4e8b7c966c76087f5c257dfb1adfa355` | — | `rejected` | `unlisted_adjunct` |
| `cf7b74761c402ee7cd01c00bef13bcf4d9451dcd6209cf8b98c3ac3470d59105` | `5b48cebe311b34c4ac464dd7698ce97b242475a11cd922994ea88ddb33890a9a` | `8ed710a57a59ea194a02ab943bff1a3d7af975a1ac281e8f5ae35ea2ef039b4a` | `changed` | — |
| `d01c190b835a5df326638ea8fac4b60508519019dd0e9f1da996db4cce48fee7` | `a678c024005e4c494b5d5fd817b759382ff37e893ff510235ff49b32d61851b1` | `72ebd65052bdd9a0fe643bccc72fad3f0b6e8d9e32978992384560bff8d17ffa` | `changed` | — |
| `d0c21fa2a28b1700c2211479d102f190e304ddaa88dd43d040520e44e0b12a56` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | `1692181560a53bdd79f9aaa27c29df86393b0e0b7391c6e35e057a1e497738b7` | `changed` | — |
| `d3dbef7794c1d68dc137f226fd40ff959ee22e90948494775fa29ff8c60152c8` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | — | `rejected` | `unlisted_adjunct` |
| `d70c500f734cbb3875674fe3b8df46a5812bc7efebe634713ddc01bb1024661c` | `68488e98367394dd660142d39e1ee685dd5ce961ec86657fba771d9ab00d77e8` | — | `rejected` | `unlisted_adjunct` |
| `da226bcbf3cfca395807d9d82dd33103c74d7becd198c9faeeb47bac3d9bcddb` | `a678c024005e4c494b5d5fd817b759382ff37e893ff510235ff49b32d61851b1` | — | `rejected` | `unlisted_adjunct` |
| `dc013ce55461871c777276bc5b4a7181b8e4047bcd8bd1d78def67e5752a70ee` | `7455a6536d24c44feb448eb93d74db6e2cd03b23d4781ed60ee931e13967bbbe` | `43de5f2705ab5996a50e75c8265d500f2e05c5536c45653c9793ef22af848e4e` | `changed` | — |
| `ddd6e8ae3a6b0d53abfdd2a5a667c4002f67c63f018119ed7b1bd31765c66cd7` | `2ac9074c82540d36c7a2b3277e28f02c5d7e067917a23dbb6da0000f0ec542d4` | — | `rejected` | `missing_child` |
| `e28390172af31a53b4867b85dfacf1c65b3abf97c2d382fb9540b9a7b31b0239` | `68488e98367394dd660142d39e1ee685dd5ce961ec86657fba771d9ab00d77e8` | — | `rejected` | `unlisted_adjunct` |
| `e482d0c26172d7bb9c5cc8ee0d1ce1086ceec7642002b8d6487421ba68c8a322` | `1ccf0bd103e2d430f68df37de0b1a1e743740bfcfb871ca871e049732bd32003` | `f7a0b6dad0d24e11f77728a62d555f6c6bc8b250d192e6fe1445dab809d559d8` | `changed` | — |
| `e5f3067bbbc944dbaf2c8ca8b645c76cb78a81e927ccb0b094780b77add1091d` | `904e98799bc58aa9775c89b4052cba791f83bd5e8928c6abeea5c10e5fbd956d` | — | `rejected` | `unlisted_adjunct` |
| `fb8f032d0a7abe9ceefaee689146579d2c7545933da126289777763a5fd10315` | `1ccf0bd103e2d430f68df37de0b1a1e743740bfcfb871ca871e049732bd32003` | — | `rejected` | `unlisted_adjunct` |

Totals: 1 unchanged, 14 changed, 27 rejected.
Rejected reasons: `missing_child` 7, `unlisted_adjunct` 19, `unsafe_frame` 1.

All changes follow the adopted frame contract; compatibility with Phase 7 output is evidence,
not a requirement to retain old behavior. The original source and frame strings are omitted.
## Regression expectations and reasons

- `In this study, we propose a compact method.` now expects `In this study, we propose [X].`;
  the previous expected frame dropped a source lead-in, contrary to ADR-0008's whole-sentence
  invariant.
- An unlisted modifier/dependent previously reported as `unmatched_content` now reports
  `unlisted_adjunct` on the generic `author_action` path, the requested named reason.
- Construction-key version expectations move from 0.1.0 to 0.2.0 with the registry version bump.
- Added accepted frames for each new anchor, approved prepositions, literal `in this ...`, purpose
  clauses, two adjuncts and exact span preservation; unsupported preposition, no-`to` `advcl`,
  three adjuncts, coordination and passive cases reject for their named/expected reasons.
- Existing reporting precedence remains covered by the Phase 7 overlap test; reporting output
  remains 203 in the same corpus run.

## Verification

Commands were run from `apps/backend` in the designated worktree:

- `ruff check .` — passed.
- `ruff format --check .` — passed; 307 files already formatted.
- `.venv\Scripts\mypy.exe --cache-dir=..\..\tmp\phase8-mypy-src-final src` — passed,
  201 source files.
- Focused: `$env:PYTHONPATH='src'; ..\..\tmp\phase3-spacy-venv\Scripts\python.exe -m pytest
  tests\unit\mining\test_phase4_constructions.py -q -p no:cacheprovider
  --basetemp=..\..\tmp\phase8-focused-final` — 29 passed.
- `$env:NLP_ENGINE='regex'; .venv\Scripts\python.exe -m pytest tests\unit -q -p no:cacheprovider
  --basetemp=..\..\tmp\phase8-unit-final4` — 593 passed, 1 skipped.
- `NLP_ENGINE=regex`, both database URLs derived from `.env.example` and set to
  `localhost:55433/aprkb_test`, `pytest tests\integration -q -p no:cacheprovider
  --basetemp=..\..\tmp\phase8-integration-regex-final` — 79 passed.
- SpaCy integration ran from `apps/backend`: database URLs were derived from `.env.example`,
  changed to `localhost:55433/aprkb_test`, and assigned to both `DATABASE_URL` and
  `TEST_DATABASE_URL`; `NLP_ENGINE=spacy`, `PYTHONPATH=src`. Command:
  `..\..\tmp\phase3-spacy-venv\Scripts\python.exe -m pytest tests\integration -q
  -p no:cacheprovider --basetemp=$tempBase`, where `$tempBase` was
  `Join-Path $env:TEMP ('phase8-spacy-integration-final-' + [guid]::NewGuid().ToString('N'))`.
  Result: 79 passed, 4 warnings in 400.17 seconds. Two earlier reruns using fresh basetemp
  directories under the worktree's `tmp` failed with Windows `PermissionError` when pytest
  created/removed nested temp directories; moving basetemp under `%TEMP%` resolved it.
- Snapshot generator: `PYTHONPATH=src ..\..\tmp\phase3-spacy-venv\Scripts\python.exe
  scripts\generate_nlp_token_snapshots.py` — completed; 85 old cases unchanged, 19 appended.
- Counts-only analysis used the supplied `corpus.py` and `allowed.json` with Phase 3 venv; output
  wrapper replaced all frame keys with hashes before printing. 51 documents, 29,344 sentences,
  12,178 kept; 121 seconds.

## Open items

- Review the complete anonymous 42-instance Phase 7/Phase 8 hash comparison above; changed and
  rejected outputs are expected when they follow the adopted frame contract.
- Review the provisional anchor/preposition/purpose/literal-phrase lists (`TODO(owner, FR-06.2)`).
- Coverage remains intentionally limited to active `we` subjects and the registered adjunct shapes;
  passive, `it`, `this paper` subjects, copula `be` and other adjunct types stay unsupported.
