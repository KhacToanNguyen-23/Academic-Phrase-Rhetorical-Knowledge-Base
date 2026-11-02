# ADR-0008: AI-assisted gold development labels from SLR articles

Status: Accepted for development workflow by owner on 2026-11-01.

## Decision

Build a development gold set from real SLR articles. AI drafts labels for every sampled item; one human reviewer makes the final decision by accepting or correcting every AI label. Only human-reviewed final labels are gold. AI cannot approve, review or publish patterns. Gold stays outside the candidate review queue.

This is an owner-approved development workflow and does not satisfy PRD FR-06.6's separate validation requirement for two editors, reported disagreement and adjudication. Do not report inter-editor agreement for this set. No agreement result or quality claim exists yet.

## Data and limits

Store article and optional sentence references, source offsets, sentence SHA-256, section-at-sampling, split and labels in `gold_items`; never copy source text into Git or audit. Resolve text only from its authoritative sentence while the hash and relevant display permission remain valid. Ingest replacement may clear the sentence reference; a hash mismatch makes the item stale.

Sample approximately 300 sentences with a fixed seed and 30% test split. Store the AI draft separately from the human-reviewed final labels. These few SLR articles are one-field development data, not a production-quality claim. Test examples are reserved from rule tuning.

## AI and rights

The selected initial provider is Groq, behind `GoldLabeler` with a null implementation. Calls are explicit and tests use a fake provider. Never log source text, prompts containing it, responses or API keys. `allows_mining` does not grant third-party AI processing. AI labeling stays disabled for real article text until the owner resolves `TODO(owner, BR-10)`; the AI draft is never treated as a human review or gold label.

For development, keep `GROQ_API_KEY` only in the local `.env` and read it when the owner explicitly requests a real Groq run. Do not add web key entry, a key-storage API, database credential storage, encryption, a master key, rotation or revoke for this phase. Never commit or log the key. No key or model is needed for mock tests. `TODO(owner, BR-10)` remains before sending data with unclear third-party processing rights.

## Update 2026-11-02

- **Meaning of `keep`:** `keep=true` means a clean running-prose sentence, not that a slot can be extracted. The sentence filter is scored on `keep` and `noise_reason`; the slot abstractor is scored only on `keep=true` sentences, with extraction coverage reported separately from field accuracy. See guideline v1 and `eval/mining/gold/DEV_PROTOCOL.md`.
- **Frame rule:** a frame is the whole sentence with each slot span replaced by its placeholder. AI drafts that do not match are marked `label_failed`; human edits are not constrained by this check.
- **Trial result:** a 10-sentence Groq trial with `openai/gpt-oss-120b` labeled all items; a manual review found frame mismatches in 3 of 7 kept items, which led to the frame check and guideline v1. This is a labeling-quality observation, not a quality claim for the mining algorithm.
