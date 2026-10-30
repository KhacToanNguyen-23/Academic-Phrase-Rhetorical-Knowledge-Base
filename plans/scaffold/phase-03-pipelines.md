# Phase 03 - Pure pipelines

Stories: P1 recommendation and validation; P2 interfaces. Dependencies: 02.

## Tasks

1. Define immutable context, PatternView and gate/scorer/rule/stage/parser/discipline interfaces per PRD section 5. Use constructor injection and build_* registries, with no FastAPI/SQLAlchemy dependencies in pure components.
2. Implement approval, retired, license, section and evidence gates in PRD order, plus guideline stub. Implement specified scorer values and aggregator renormalization for None or zero weights, preserving null breakdowns. Read fallback tiers from YAML and keep diversifier stub; do not invent journal similarity data.
3. Run V01-V08; V02 shares EvidencePolicy and lexicon with the gate, with severity from YAML. Other rules return PASS and retain TODO plus requirement IDs.
4. Implement configured sentence length/citation filter, pass-through remaining stages and candidate writer requiring source IDs through a port. Add parser interfaces, null discipline source and fingerprint stub.

## Verification

- Unit test pass and fail for each implemented gate, aggregator renormalization and zero weights, V02 with 'This proves ...', and gate/V02 consistency for identical input.
- Test citation filtering and rejection of missing candidate sources; verify registry ordering and requirement IDs on stubs. Pure tests do not require a database.

## Review additions

- Apply the same gates to candidates from every fallback tier, deduplicate pattern versions across tiers, and enforce the requested limit. Test these properties.
- Handle missing or unknown ordered evidence values and an all-zero active weight configuration explicitly; test and document the chosen fail-closed/error behavior without inventing business thresholds.
