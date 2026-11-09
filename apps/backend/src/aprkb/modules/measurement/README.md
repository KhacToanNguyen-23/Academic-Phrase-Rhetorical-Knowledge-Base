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
- Not implemented: mining measurement mentions from METHODS sections and an FR-08.2 validator rule.
