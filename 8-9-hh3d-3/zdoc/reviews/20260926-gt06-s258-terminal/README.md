# S258 — interrupted O1 attempt, not acceptance

AUTHORITY=0. Campaign `gt06-s258-o1-01` used source closure
`03f5331ef335fe7c4328d636c07340b2814ebac6072c26872af4aaebb8f70c1e`
and profile `65127279434d8dc96819ac01cb42422ca7a7cc49e944162677b34d6a68f2fd0a`.
It captured batch 0 of pair 0; batch 1 was incomplete. No measured batch,
complete pair, GT06 acceptance, leak attribution or PASS is claimed.

The coordinator launched with memory/commit-only preflight after one positive
review. A later independent review found O1.8 app-inventory enforcement missing.
Browser/WSL/chat processes were observed; the coordinator interrupted the
terminal session. This is a harness/preflight omission and coordinator abort,
not an O1.7 INFRA_ABORT or a product-counter failure. The invocation must never
resume or donate partial samples to a new campaign. The former TICK=yes is
superseded by the finding for launch readiness; neither review accepts GT06.

Import PID 15204 has actual exit 0 and a closed, zero-count Job in
`run-00-attempt-01/import-host/capture.json`. Host PID 1268 and editor PID 22492
have start records but no process-exit/capture/terminal-cleanup receipt.
Their actual exits, natural exits, Job closure and released handles remain
UNKNOWN. Current process absence does not repair these missing observations.
The exec wrapper returned 1 after interruption; it is not a target-exit proof.

Original 198 raw files (18,631,361 bytes) remain unchanged in
`studio/.local/reviews/gt06-s258-o1-01/`. Added `raw-manifest.json` SHA256:
`f0c2bb917a28143f818c621eee3c70becec03ad5dd57432ec6f4e0253877d4ab`.
Ignored archive `studio/.local/archives/gt06-s258-o1-01-terminal.zip` has 199
members and SHA256 `5ccdbfd8147fb0e27503ff2b2c7095d622fad7fc896b415eb056480dfc490d82`.
Every original file and archive member was read back and matched its hash.
No dumps, raw logs, cache or binaries are committed.

Repair: preflight schema 1.1.0 inventories known browser, active WSL and chat
process names/PIDs; unknown enumeration or snapshot-close errors reject launch.
Memory >=8 GiB and commit <=80% still apply immediately before each pair.
The coordinator app is necessary to run the task; idle WSL services and generic
WebView processes are not classified as active user applications. This is a
bounded known-app check, not proof that every possible background load is absent.
The native implementation follows Microsoft
[Toolhelp snapshot](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-createtoolhelp32snapshot)
and [process enumeration](https://learn.microsoft.com/en-us/windows/win32/api/tlhelp32/nf-tlhelp32-process32nextw)
contracts, checks the native handle width and releases the snapshot handle.

Use the checked demand-only `tests/replay/campaign_task.ps1` launcher for the
next fresh ID after source/critic/environment checks. Use the runner's Stop
latch and wait for terminal cleanup; do not use a terminal Ctrl-C as evidence
of controlled cleanup. Timeout 7410 seconds and measurement gates are unchanged.
