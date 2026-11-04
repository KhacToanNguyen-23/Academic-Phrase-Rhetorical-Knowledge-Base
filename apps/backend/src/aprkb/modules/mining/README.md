# Mining scope

Implement rule-based sentence extraction in the worker with pending candidates, source provenance and two-round review. `NLP_ENGINE=regex` remains the default; `NLP_ENGINE=spacy` runs the rule-first boundary resolver and stores token features at ingest. Phase 3 consumes valid stored tokens in `SentenceFilter` and `SlotAbstractor`; invalid or missing tokens fall back to the regex path. Check mining rights before source access; no mining writes to patterns or versions. Self-authored mock fixtures exercise the flow; real-article gold and quality evaluation await the external article API. See [ADR-0007](../../../../../../doc/adr/0007-rule-based-slot-abstraction.md) and [ADR-0010](../../../../../../doc/adr/0010-spacy-ingest-token-features.md).

The `extraction` module (`/extract` page) queues this mining per import batch and lets one reviewer accept phrases into `approved_phrases`; see [ADR-0009](../../../../../../doc/adr/0009-phrase-extraction-page.md).

The spaCy shared-token-feature spike is recorded in [the round-1 report](../../../../../../plans/reports/261104-spacy-nlp-spike-report.md), [the round-2 report](../../../../../../plans/reports/261104-spacy-nlp-spike-round2-report.md), [the phase-2 report](../../../../../../plans/reports/261104-spacy-phase2-report.md), and [the phase-3 report](../../../../../../plans/reports/261104-spacy-phase3-report.md).
