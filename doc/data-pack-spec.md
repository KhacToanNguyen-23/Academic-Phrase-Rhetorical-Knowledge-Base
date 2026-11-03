# Offline-to-Online Data Pack v0.1

This is a normative English summary of the accepted Vietnamese regulation. The Vietnamese regulation remains authoritative.

## Layout

A pack directory contains `manifest.json` and `patterns.json`. Manifest fields are `pack_version` (`0.1`), `taxonomy_version`, `producer`, UTC `created_at`, `counts` (`patterns`, `versions`), and `files` containing the `patterns.json` SHA-256. JSON is UTF-8. Output is sorted for stable diffs.

Each pattern has stable `pattern_id`, approved `status`, full natural-key `intent` path (`taxonomy_version`, `section`, `move`, `step`, `intent`), `current_version_no`, and append-only `versions`. Each version has stable `version_id`, consecutive `version_no`, `canonical_frame`, typed `slots`, `claim_type`, `epistemic_strength`, optional `change_note`, `usage`, optional `variants`, and `provenance`. Usage requires nonempty section codes; empty genres means unrestricted genres. Frames use `{slot}` placeholders exactly matching slot keys.

Provenance is `authored` or `mined`. Mined versions require a mining-permitted license other than `DEV-UNVERIFIED`, an article key (`doi` or `source` plus `external_id`), positive `source_sentence_count`, and exactly two approving reviews. Optional `section_code` and `occurrence_hash` are metadata only. Reviewer names, roles and times are included. Article/sentence UUIDs and source text are prohibited. All references except pattern/version IDs use natural keys.

## Findings

Errors: E01 manifest/digest/counts; E02 taxonomy version; E03 intent path; E04 status; E05 claim/evidence enum; E06 epistemic strength; E07 sections; E08 genres; E09 placeholders; E10 slot type; E11 provenance; E12 license rights; E13 mined review rounds; E14 extra fields, provenance UUIDs or source text; E15 changed stored version (import only); E16 version sequence. Warnings: W01 no variants; W02 no evidence minimum; W03 missing slot labels/instructions/examples; W04 unrestricted genres; W05 no discipline field; W06 forbidden contexts with undefined semantics.

## Process and versioning

Offline runs `aprkb validate-pack <directory>` without a database. Online runs `aprkb init-reference`, previews with `aprkb import-pack <directory> --dry-run`, then imports with `aprkb import-pack <directory>`. Import is transactional and idempotent; changed known versions fail E15. Each changed import writes one content-free audit event. Export with `aprkb export-pack --out <directory> --only-approved`; generate schema with `aprkb export-pack-schema`. v0.1 is append-only; incompatible contract changes require a new pack version and transition documentation.
