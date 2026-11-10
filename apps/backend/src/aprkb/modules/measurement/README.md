# measurement

Separate Metric & Measurement catalog (ADR-0015). It holds metrics, measurement methods and
protocols, imported from the self-authored `data/seed/measurement_catalog.json`.

- `importer.py`: a strict parser that validates everything before writing anything. The import is
  idempotent (an unchanged sha256 is a no-op) and upserts entries by `code`. Relations are replaced
  in full. Missing codes are reported, never deleted. Each import writes one content-free audit
  event.
- `repository.py` / `service.py` / `router.py`: the read API (`/v1/measurements`, client role) and
  curator routes under `/v1/admin/measurements` for import and slot-link review.
- Slot links bind an entry to `(pattern, slot)`. A proposed link is hidden. An approved link appears
  only as a suggestion via `/v1/measurements/slot-suggestions`; render never auto-fills it.
- Kinds, relation rules and link statuses live in `policies/measurement.yaml` (`TODO(owner, Task-3)`).
- `metric_check.py`: a pure FR-08.2 check, used by `/v1/validate` only while the flag is on.
  It is report-only: it lists catalog metrics named in the text but not in the supplied
  slots or context.
- `purge_catalog` / `measurement-purge` remove all catalog data in one audited transaction.
- Links may omit `slot_name` (pattern-level), for slot-less APB Methods templates.
  `link_proposer.py` / `measurement-propose-links` create *proposed* `term_match` links
  only; a curator must approve each one.
- Not implemented: mining measurement mentions from corpus METHODS sections.
