# Spec: Scaffold AP-RKB

**Date:** 2026-10-30
**Status:** Draft

## Problem Statement

Nh?m c?n m?t backend AP-RKB ch?y v? ki?m th? ???c, v?i ranh gi?i module, h?p ??ng API v? d? li?u n?n ?? ti?p t?c ph?t tri?n nghi?p v?. Scaffold ph?i th?c hi?n c?c h?nh vi t?i thi?u ???c ch? ??nh, gi? c?c thu?t to?n ch?a c? d??i d?ng stub.

## User Stories

- **[P1]** L? developer, t?i mu?n kh?i ??ng PostgreSQL, migrate, seed v? ch?y API t? repo s?ch. Accepted when: chu?i l?nh ? m?c 12 PRD th?nh c?ng v? `/docs` hi?n th? c?c endpoint m?c 7.
- **[P1]** L? API client, t?i mu?n nh?n g?i ? v? k?t qu? validation c? gi?i th?ch. Accepted when: pipeline ?p d?ng gate, tr? breakdown v? fallback tier; V02 block c?u ch?a ?prove? v?i `single_study` theo ch?nh s?ch m?u.
- **[P1]** L? admin, t?i mu?n qu?n l? quy?n truy c?p v? theo d?i thao t?c ghi. Accepted when: thi?u key tr? 401, sai role tr? 403, thao t?c ghi c? audit event v? key plaintext ch? hi?n th? m?t l?n khi t?o.
- **[P1]** L? curator, t?i mu?n ingest v? mine m?t file text ?? t?o candidate c? ngu?n. Accepted when: upload `.txt` r?i ch?y worker t?o ?t nh?t m?t Candidate c? `source_sentence_ids`, kh?ng ghi tr?c ti?p pattern/version.
- **[P2]** L? developer, t?i mu?n c? c?c interface v? stub cho discipline, guideline, fingerprint v? mining ?? m? r?ng sau. Accepted when: registry n?i c?c th?nh ph?n v? c?c stub c? TODO k?m m? y?u c?u.
- **[P3]** Ngo?i ph?m vi: mining th?c, OpenAlex, fingerprint th?c, giao di?n admin, deploy v? CI/CD.

## Functional Requirements

1. **FR-01:** Gi? b? c?c repo hi?n c?; ?nh x? c?c module v? file trong SCAFFOLD_PRD v?o c?u tr?c ??. C?c quy?t ??nh ch?c n?ng c?a PRD ???c ?u ti?n cho scaffold.
2. **FR-02:** D?ng Python 3.12, FastAPI, Pydantic v2, SQLAlchemy async, Alembic, PostgreSQL 16 v?i pgvector; jobs l?u trong Postgres v? worker polling v?i `FOR UPDATE SKIP LOCKED`; blob local qua interface.
3. **FR-03:** T?o model v? migration ban ??u cho to?n b? entity m?c 4 PRD, g?m reference enum, version append-only v? extension vector. Kh?ng cung c?p API update/delete pattern version.
4. **FR-04:** Cung c?p interface v? registry m?c 5?6 PRD; gate, scorer, rule, stage l? class thu?n, kh?ng truy v?n DB; `PatternView` n?p tr??c v? guideline policy ???c cache.
5. **FR-05:** Recommendation ch?y gate theo th? t? PRD, fallback, scorer v? aggregator chu?n h?a tr?ng s? khi thi?u ?i?m; tr? breakdown, exclusions, fallback tier, policy version v? ghi log.
6. **FR-06:** Validation ch?y V01?V08; V02 d?ng chung EvidencePolicy v?i EvidenceGate v? lexicon versioned. C?c rule TODO tr? PASS.
7. **FR-07:** License check ch?n mining kh?ng ???c ph?p; splitter gi? offset; sentence filter l?c ?? d?i v? tr?ch d?n; stage c?n l?i gi? batch; candidate writer y?u c?u source sentence IDs. Ch? review ?? hai v?ng approve m?i t?o version t? candidate.
8. **FR-08:** Cung c?p to?n b? route, schema, role v? tr?ng th?i th?c thi ? m?c 7 PRD; ph?n ch?a tri?n khai tr? 501. M?i response c? request ID v? l?i theo ??nh d?ng chung; ghi audit cho thao t?c ghi.
9. **FR-09:** N?p v? ki?m tra schema policy YAML khi kh?i ??ng; policy sai khi?n app kh?ng kh?i ??ng. Tr?ng s?, ng??ng v? t? v?ng nghi?p v? n?m trong policy; b?o to?n TODO(owner).
10. **FR-10:** Seed idempotent theo th? t? reference enums, taxonomy, patterns v?i d? li?u m?u v? license nh? m?c 9 PRD; cung c?p bootstrap admin key v? c?c l?nh dev t??ng ???ng m?c 11.
11. **FR-11:** T?o unit/integration test v? 12 acceptance test theo m?c 10 PRD; test acceptance ch?a c? h?nh vi ???c bao ph? ph?i skip v?i TODO, test ?? ???c bao ph? d?ng l?i logic ki?m th?.

## Non-Functional Requirements

- **Performance:** Kh?ng ??t ch? ti?u latency hay throughput m?i ngo?i PRD; ?o v? b? sung ? giai ?o?n sau.
- **Security:** API key qua `X-API-Key`, hash khi l?u; RBAC `admin > curator > reviewer > client`; kh?ng log key ho?c to?n v?n b?i b?o.
- **Data integrity:** Pattern version append-only; audit cho thao t?c ghi; UTC/timestamptz; seed ch?y l?p kh?ng t?o b?n ghi tr?ng.
- **Availability:** Ch?a ??t SLO; health endpoint ki?m tra k?t n?i DB.
- **Maintainability:** Ruff, formatter v? mypy strict cho backend; stub mang m? y?u c?u; README c? b?ng truy v?t PRD.

## Success Criteria

- [ ] T? repo s?ch, chu?i `make up`, `install`, `migrate`, `seed`, `bootstrap-key`, `lint`, `test`, `run` theo m?c 12 PRD th?nh c?ng.
- [ ] `/docs` li?t k? to?n b? endpoint m?c 7; health tr? 200 khi DB k?t n?i ???c.
- [ ] Recommendation seed lo?i draft, retired v? mined license proprietary; tr? breakdown v?i discipline v? journal_genre l? null.
- [ ] V02 block ?prove? v?i single_study; test consistency x?c nh?n EvidenceGate v? V02 d?ng c?ng ch?nh s?ch.
- [ ] Upload `.txt` v? mine qua worker t?o ? 1 candidate c? source sentence IDs.
- [ ] C?c test b?t bu?c m?c 10 pass; 12 acceptance test t?n t?i v? test ch?a tri?n khai ???c skip ??ng l? do.
- [ ] Kh?ng hard-code tr?ng s?, ng??ng ho?c lexicon nghi?p v? trong backend; m?i stub c? TODO v? m? y?u c?u.

## Out of Scope

- Mining classifier, NER, LLM, clustering th?c; OpenAlex adapter v? journal fingerprint th?c.
- Parse PDF th?c, admin UI, deploy, CI/CD, monitoring, publish taxonomy, ablation.
- B?a n?i dung nghi?p v? cho c?c TODO(owner) ho?c sao ch?p c?u t? b?i b?o c? b?n quy?n.

## Assumptions

- SCAFFOLD_PRD l? ngu?n ?u ti?n cho giai ?o?n scaffold; ngo?i l? ???c ng??i d?ng ch?n l? gi? c?u tr?c repo hi?n c?.
- C?c gi? tr? evidence, lexicon, seed v? taxonomy trong PRD l? d? li?u th? nghi?m, kh?ng ph?i ch?nh s?ch ?? ???c ch? s? h?u duy?t.
- C?c chi ti?t ch?a ch?t nh? t?n rule V01 v? V03?V08 v?n l? TODO(owner), kh?ng c?n vi?c d?ng stub.
- K? ho?ch s? ki?m tra c?ch ?nh x? c?u tr?c, x? l? c?u h?nh Celery/Redis c? v? th?c hi?n parser text t?i thi?u cho lu?ng DoD m? kh?ng m? r?ng ph?m vi.
