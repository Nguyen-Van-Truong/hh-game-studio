# S232 — post-ACK counter-probe diagnostic preflight

This packet records a bounded diagnostic run after the S231 retained-object
review. The native fixture source now enters a short `POST_ACK_PROBE` phase
after a validated host ACK. The phase waits for the existing bounded settle
window and writes an ignored `hh-studio.native-counter-probe` artifact with
the ACK and settled object/resource counters. The formal joint receipt remains
bound to the ACK sample; this supplemental artifact cannot make a run pass.

Run `gt06-s232-counter-probe-syntax-02` loaded the fixture and completed one
direct semantic editor cycle. It exercised the modified GDScript parse and
runtime path, but diagnostic mode has no host ACK, so it did not enter
`POST_ACK_PROBE`. Editor and import processes both reported actual exit 0;
both owned Jobs were zero/closed with no retained Job handle. These receipts
do not enumerate every wrapper or observer handle.

The executed diagnostic closure contains **39 source files**, with SHA256
`3d5beb5b459dc12f15a3a02f758ee23558d3e34d50568afbe7716549bcd6d020`.
The separate formal campaign closure contains 53 source files; this diagnostic
does not verify that formal closure or its host/API workload.

This is source and cleanup preflight only. It is not a formal GT06 run, does
not establish object ownership or a leak root cause, and does not change the
10×35 gate, timeout, baseline, profile, counter, or RSS criteria. The added
post-ACK settle window changes cadence by at least 1.1 seconds in the formal
path, and this one-cycle diagnostic did not exercise that path. No repaired
boundary is proven and this packet authorizes no formal campaign or retry.
It remains diagnostic/terminal evidence only.

The raw diagnostic is retained at
`studio/.local/reviews/gt06-s232-counter-probe-syntax-02` and its sealed local
archive is `studio/.local/archives/gt06-s232-counter-probe-syntax-02-s233-terminal.zip`.
The raw manifest and archive are Authority 0.

Run `python -B zdoc/reviews/20260924-gt06-s232-counter-probe-diagnostic/verify.py`
from `8-9-hh3d-3` for a read-only check. The verifier checks packet hashes,
exact raw/archive membership and bytes, derives the diagnostic source count
and closure from archived source bytes, and cross-checks target exits and Job
cleanup against the sealed stage receipts. It also verifies that the native
output is one diagnostic cycle with no host ACK or post-ACK probe artifact.
This verification is not a GT06 acceptance verdict.
