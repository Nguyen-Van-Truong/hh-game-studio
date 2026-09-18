# S93 response sampling repair / S91 failed diagnostic

AUTHORITY=0. Folder numbering began during S92 routing work; source repair is S93.
No GT-06 acceptance, benchmark dataset, or independent final verdict.

S91 terminated at batch 16 after 17 partial batches with CAMPAIGN_STATUS_GAP.
The host maximum was 2072.4595 ms; native maximum was 601.142 ms. The first
interval combined 1214.881 ms before submit with an 857.5781 ms admission.
See `gap-analysis.md`. Discovery and lease had actual responses, but the old
producer did not timestamp them, unlike auxiliary lookup and Cancel. No old
timestamps can be reconstructed: S91 remains FAIL and is never promoted.

The repair keeps the original batch start/end, 2000 ms threshold, command mix,
timeouts, durability, native ACK and counters. Command schema 1.2.0 records
ordered discovery/lease request-start and actual response timestamps. It also
records the previously unbound Cancel submit response. The validator requires
the exact multiset of start/end plus all recorded responses; inserting extra
progress timestamps, missing setup, reordering phases or reusing old schemas
is rejected. A synthetic 2100 ms setup stall remains above the unchanged gate.
These changes affect only `benchmark_commands.py` and `benchmark_assembly.py`
in the 51-file runtime closure, now
`e05d69137d9b6ff303bf75abe47cf981ad336c41ab7945392cd6f8ae6df0e601`.

`unit-01` ran 73 targeted tests: 72 passed and one old expectation failed because
an unexpected diagnostic is now rejected during setup, before any command.
The expectation was corrected, with the failed run retained. `unit-02` reran
all 17 command tests successfully. The other 56 assembly/campaign tests passed
in unit-01 and their tested code/inputs did not change. Both owned runs have
actual target exits, wrapper exit 0, verified process trees and unchanged source
within each run; unit-01's target exit is truthfully 1.

`startup-probe` froze S91 baseline dependencies before editing runtime. Two
separate owned Python processes each ran two ten-command diagnostics against
a fresh project and a copy of the same 16,867,309-byte S91 journal. Both completed,
original history and source remained unchanged, actual target/wrapper exits 0,
and trees were verified. Baseline maximum gaps were 165.7822/170.3227 ms;
repaired gaps 171.5723/156.8794 ms. Neither reproduced the 2072 ms event, so
there is no environment/root-cause or throughput claim. Per-phase spans and
loaded-module hashes are retained. Wrapper timings are supplemental and not
substituted for the producer's actual response timestamps.

Failure seal `515d48cf5295fb6653d6e3588d14b4e3a079e6e17dd6c186e2f2d57314b76308`
contains 159 exact copies and checks 170 originally declared raw artifacts.
`seal_s91.py --verify` checks the preserved immutable source, not the repaired
working source. External retained-handle exits supplement the missing inner
editor exit without claiming it was natural. See `terminal-audit.md` and the
separate scheduler terminal receipt. All 17 ACK ObjectDB counts were 71128;
only the baseline sparse snapshot exists. The earlier S86 +2 cause remains
unresolved; stable counters do not establish absence of leaks.

Two implementation workers later returned a workspace-credits error. Their
partial files were retained and completed by the coordinator, with no invented
critic verdict. Game-plan work was already saved in commit 135cc588.

The separate `startup-probe/result-full` run exercised all 1000 commands and
200 effects against another copy of the same history; the strict schema 1.2.0
validator passed. Maximum host gap was 487.04 ms. Actual target49788/wrapper7048
exited0 with verified tree and unchanged source/history. It is supplemental,
not the native campaign. Baseline/repaired source trees and copied journals
remain local; source maps and source commits reproduce them without committing
large copies of journal history.
