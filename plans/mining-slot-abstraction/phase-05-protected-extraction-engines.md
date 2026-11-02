# Phase 05 — Runtime mining

Status: implemented; unit tests pass. PostgreSQL upload/ingest/mine integration awaits `TEST_DATABASE_URL` for `aprkb_test`.
Gate: G1 approved. Execute phases 04 → 05 → 06.

`SlotAbstractor.extractability_reason(text)` (2026-11-02) cho biết câu có trích được không: `None` nếu được, hoặc `no_reporting_verb`, `no_that`, `no_subject`, `subject_too_long`, `clause_too_short`. `_extract` dùng cùng bước định vị (`_locate`) nên hành vi trích không đổi. Evaluator dùng hàm này để thống kê lý do một câu sạch không được trích. Trên 10 nhãn nháp, phần lớn câu bị bỏ vì `no_reporting_verb`; chưa mở rộng danh sách động từ hay mẫu không có *that* (chờ số liệu từ gold được duyệt).

Regex-only sentence extraction with fixed conservative span policy, positional slots, protected wording and offsets. spaCy/NER deferred TODO(owner, FR-06.2).

Use TDD and self-authored fixtures. No new endpoints, pattern/version writes, raw source in public outputs/logs/audit, or fabricated classifier output. Verify offsets, tense/strength/ownership negative pairs, policy validity, and upload → ingest → mine integration.
