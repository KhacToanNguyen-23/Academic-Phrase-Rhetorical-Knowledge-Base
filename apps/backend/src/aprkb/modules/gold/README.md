# Gold development workflow

Phase 02 stores deterministic references and hashes, not article text. Gold detail reads sentence text only when the current license allows display and the sampled hash still matches. Human decisions are audited by item and changed field without sentence text.

Phase 03 drafts are opt-in. `GOLD_LABELER=null` is the default. The owner selected `openai/gpt-oss-120b`; the policy provider is set to Groq. Before a real run, verify third-party processing rights, set `GOLD_LABELER=groq`, keep `GROQ_API_KEY` only in the ignored local `.env`, and set `GROQ_ALLOW_EXTERNAL_PROCESSING=true`. Rate settings remain provisional TODOs. Do not use `allows_mining` alone as permission to send article text to Groq.

Queue a draft job with `POST /v1/admin/gold/samples/{sample_batch}/label`. The worker checks rights before reading source sentences, checks source hashes, validates every response with Pydantic, and stores drafts as `draft`. Provider errors and audit snapshots never include sentence text, prompts, responses, or keys. Mock tests use `httpx.MockTransport`; they do not make network requests.

One human reviewer approves, edits, or rejects each AI draft in `/gold`. Only `approved` items are read by `eval-mining`. The development workflow uses one reviewer and does not satisfy FR-06.6's two-editor validation requirement. No evaluation report exists until human-approved labels are present.
