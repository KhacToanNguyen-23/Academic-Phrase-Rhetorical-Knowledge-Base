# Mining scope

Implement regex sentence extraction in the worker with pending candidates, source provenance and two-round review. The policy uses fixed conservative spans and positional slots. Check mining rights before source access; no mining writes to patterns or versions. spaCy and NER are deferred (`TODO(owner, FR-06.2)`). Self-authored mock fixtures exercise the flow; real-article gold and quality evaluation await the external article API. See [ADR-0007](../../../../../../doc/adr/0007-rule-based-slot-abstraction.md).

The `extraction` module (`/extract` page) queues this mining per import batch and lets one reviewer accept phrases into `approved_phrases`; see [ADR-0009](../../../../../../doc/adr/0009-phrase-extraction-page.md).

The spaCy shared-token-feature spike is recorded in [the spike report](../../../../../../plans/reports/261104-spacy-nlp-spike-report.md) and is not wired into this pipeline.
