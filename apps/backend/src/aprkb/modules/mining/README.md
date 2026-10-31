# Mining scope

Implement regex sentence extraction in the worker with pending candidates, source provenance and two-round review. The policy uses fixed conservative spans and positional slots. Check mining rights before source access; no mining writes to patterns or versions. spaCy and NER are deferred (`TODO(owner, FR-06.2)`). Self-authored mock fixtures exercise the flow; real-article gold and quality evaluation await the external article API. See [ADR-0006](../../../../../../doc/adr/0006-rule-based-slot-abstraction.md).
