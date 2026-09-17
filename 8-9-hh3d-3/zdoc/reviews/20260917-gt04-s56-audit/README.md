# S56 component evidence audit

File-only verification passed for `20260917-gt04-s56-deadline-02` and
`20260917-gt04-s56-writer-01`. Both complete 129-file source snapshots have
closure `71332451f3914f42f3a35dc8702a1c0eb3cb3cb6d99adfa4b8ca317373dd8162`.
This is a scoped component audit, not GT-04 acceptance.

Run from the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-s56-audit/verify_evidence.py
```

The verifier reads captured files and imports only the frozen snapshot. It
reuses its producer completion gates, then independently binds raw unit
inventories and completion logs, target/wrapper exit records, GUI process
identity, pinned launch source, closed/empty owned Jobs, HTTP bytes, and
decoded ledger history. No engine is launched, no native handle is opened,
and no Journal constructor is called; journal checks use the frozen pure
record decoder and history validator.

Verified evidence:

- 440 full Blender unit tests and 174 focused writer unit tests completed
  without failures, errors, or skips. Raw target and wrapper exits are zero.
- 19 deadline native checks passed, with expired/malformed envelopes leaving
  the observed scene unchanged and retries preserving the original receipt
  after its original deadline.
- The separate HTTP client captured 23 calls and passed 31 checks; the native
  parent passed 7 checks. GUI, parent, and CLI process exits and owned Job
  cleanup agree with their raw capture records.
- Seven successful HTTP operations bind in order to exactly seven common
  ledger INTENT/terminal pairs. Terminal bytes equal the HTTP wire bytes.
  Creation, transform, material, Undo, Redo, and final inspect observations
  bind to the admitted requests, native owner, source, and revision chain.
- Duplicate and lookup receipts remain byte-identical. Conflict, foreign
  session, forbidden write, expired deadline, and wrong Stop route traces
  carry the expected denial without an observation. Discovery exposes only
  connected inspect/edit operations, then no operations after Stop.

`portable-artifacts.json` maps paths relative to `8-9-hh3d-3` to plain SHA-256
values. It includes the two complete frozen snapshots and the consumed
evidence. It excludes generated audit/checkpoint outputs to avoid a
self-referencing manifest.

Only two closed journal streams are copied here: `client-commands.jsonl`
(15 records: configuration plus seven INTENT/terminal pairs) and
`writer-leases.jsonl` (three native session/lease/Stop records). Their exact
bytes match the original package inventories. The copies are decoded and
checked for credential-shaped fields before preservation. They allow replay
without staging private journal directories, guards, caches, or native work
files. Existing copies must match and are never overwritten by the verifier.

Limits remain explicit: seven native submission counter checks are captured
harness observations, not a raw IPC packet recording. The original harness
performs known-secret byte comparisons; this audit adds structural credential
and bearer checks but cannot reconstruct withheld credentials. Native
float-preserving revision tokens stay opaque; declared JCS observation hashes
are recomputed. Public ACK and durable scene/publication claims remain false;
save/export integration and final GT-04 acceptance are outside this audit.
