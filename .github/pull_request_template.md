## Scope

- Linked issue/plan:
- Summary and intentionally excluded work:
- Risk: tiny / normal / high-risk

## Verification

- [ ] Backend: `make lint`
- [ ] Backend: `make test` with `TEST_DATABASE_URL` pointing to `aprkb_test`
- [ ] Frontend checks relevant to this change
- Evidence, including skipped or unavailable checks:

## Release impact

- Database migration: none / expand / migrate / contract
- N-1 compatibility and rollback impact:
- Worker drain required: yes / no, with reason
- `BLOB_DIR` or persistent-storage impact:

## Security and data handling

- New or changed secret/configuration names (never values):
- [ ] If applicable, logs and artifacts exclude API keys, article/manuscript text, and uploaded blobs; otherwise explain N/A below
- [ ] If applicable, mining rights are checked before blob reads or parsing; otherwise explain N/A below
- N/A reasons:

## Documentation and ownership

- Runbook/README changes:
- CODEOWNER or operational approval required:
- Break-glass change reference, if applicable:
