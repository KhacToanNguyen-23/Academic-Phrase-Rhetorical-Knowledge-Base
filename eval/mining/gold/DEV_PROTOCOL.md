# DEV_PROTOCOL — Deferred draft

Deferred until the external article API is available. Future gold will be sampled from real articles, not written by editors. FR-06.6 requires two editors, reported disagreement and adjudication. No gold, labels, scores or human approvals have been created. Current implementation uses self-authored mock fixtures only.

**[Proposal]** AI drafts labels for sampled real-article sentences; two editors independently review and correct the drafts. Approximately 20% of sentences are labeled by the editors without seeing an AI draft; use that subset to measure AI–human κ and investigate anchoring. Retain independent editor decisions, report disagreement and adjudication as required by FR-06.6. Do not infer or fabricate a score. AI never counts as an editor or reviewer and makes no final decision.

Daily-review AI suggestions are enabled only after AI has been measured against human-checked gold. Before any AI processing, the owner must approve LLM scope and confirm license permission for an external provider or use a self-hosted model; `allows_mining` alone is insufficient for third-party processing. Do not log source sentences, prompts containing them or API keys; version model, prompt and thresholds in policy YAML and mark provisional values `TODO(owner)`. **[Proposal]**
