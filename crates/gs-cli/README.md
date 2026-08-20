# gs-cli

Library + thin binary behind `tools/gs.ps1`. Talks to the editor bus:

- read `.gs/runtime/endpoint.json` (token stays in memory; `Debug` redacts it)
- refuse a stale pid (do not hang)
- TCP `127.0.0.1` → `session.hello` → JSON-RPC 2.0 NDJSON
- auto-insert `command_id` (ULID) on mutating/job calls and print it

Does **not** contain document, WAL, or scene logic. No second dispatcher.

## Offline verbs (no bus / no `endpoint.json`)

- `gs-cli doctor` — imagegen preflight (MASTER 8.5). Exit 0 only if Python
  plus ComfyUI **or** a remote-C key is usable. Never prints API keys.
  Test overrides: `GS_DOCTOR_FORCE=ok` / `missing`.
- `gs-cli --root PATH jobs-claim --worker-id ID`
- `gs-cli --root PATH jobs-heartbeat --job-id ID --worker-id ID`
- `gs-cli --root PATH jobs-finish --job-id ID --result-file result.json`

These call `gs-jobs` only. The imagegen worker must not read `endpoint.json`.

Equivalent: `cargo run -p gs-cli -- doctor`.

