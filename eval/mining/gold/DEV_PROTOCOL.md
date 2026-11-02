# Gold development protocol v0 — Deferred draft

## Source and sample

Use the reproducible sample from real SLR articles; do not write or copy sentences into this repository. The current target is approximately 300 sentences with a fixed seed and 30% `test`, stratified within each kept section and the filtered-sentence group, with the total test count kept exact. About 10% of each batch comes from sentences the mining filter rejects, spread evenly by rejection reason; the rest is spread evenly across sections of retained sentences. If either pool is short, the other fills its quota. Proportions live in `apps/backend/src/aprkb/policies/gold_sampling.yaml`. `allows_mining` alone does not authorize sending article text to an external AI provider.

The batch creation audit records the number of filtered items and the sampling policy version. From the repo root, remove a sample with `uv run --directory apps/backend python -m aprkb.cli delete-gold-batch --sample-batch <id>`; it refuses to delete if any item has AI or final labels and records `gold.sample.delete` with the deletion.

## AI draft and human decision

When the owner explicitly requests a real Groq run, the labeler reads `GROQ_API_KEY` from the local `.env` and drafts labels for every sampled item. One human reviewer accepts or corrects every draft and makes the final decision. The AI never approves and never counts as a human review. No key or model is needed for mock tests.

No κ, disagreement rate or quality score is to be reported until labels have been collected and analyzed. This one-reviewer development protocol does not meet FR-06.6's separate validation requirement for two editors, reported disagreement and adjudication.

## Evaluation metrics

`eval-mining` reports the two algorithms separately:

- `sentence_filter` scores `keep` (precision, recall, confusion) and compares gold `noise_reason` with the filter's reject reason as a raw confusion table, so no mapping between the two vocabularies is assumed.
- `extraction` runs the stages after the filter on every `keep=true` sentence and reports `coverage` (the share the slot abstractor can extract) with a count per `extractability_reason`. `accuracy`, `confusions` and `slot_f1` are computed on the extracted sentences only; read them together with `coverage`.

Guideline v1 changed the meaning of `keep` and the `frame` rule. Labels drafted under v0 are not comparable and should not be approved as gold without review.

## Privacy and versions

Never log source sentences, prompts containing them, provider responses or API keys. Keep the provider key out of code, Git, API responses and audit events. `.env` is local and gitignored. Do not build web key entry, server-side key storage, encryption, a master key, rotation or revoke for this development phase. Version model, prompt and provisional thresholds in policy YAML with `TODO(owner)` markers. `allows_mining` alone does not authorize third-party AI processing; retain `TODO(owner, BR-10)` for unclear rights.
