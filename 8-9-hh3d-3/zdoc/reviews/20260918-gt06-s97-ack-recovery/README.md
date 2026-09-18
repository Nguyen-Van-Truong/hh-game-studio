# S97: preserve S96 ACK-read failure and isolate the next repair

AUTHORITY=0. Diagnostic evidence only; no GT06 acceptance or final critic verdict.

S96 `gt06-s96-coupled-phases-01` terminated at 2026-09-18 16:26:32 UTC.
It retained 17 complete joint/ACK rows (0–16), and all 1,000 HTTP commands and
100 native cycles in batch17. Native failed `BENCHMARK_HOST_ACK_READ` before
ACK17 receipt and fresh counters; the host reported `CAMPAIGN_NATIVE_FAILURE`.
The code conflated a null `FileAccess.open` and a short `get_buffer`. Neither
branch nor the OS error was recorded. Later valid ACK17 bytes do not distinguish
them or prove that Godot read the file at the failing instant.

The HTTP recorder reports zero transport failures. All 18 command batches are
COMPLETE, with 12,631 lookup attempts and no UNKNOWN; the largest response gap
is 1220.1735 ms. This is a different failure from S93's lookup timeout. Its
last512 phase events cover only the final0.992 seconds, not run-wide phase
maxima. See `http-phase-analysis.md` and its hash-bound derived JSON.

Native ACK counters remain71128 objects/6 resources for the 17 retained ACKs.
Only baselineACK4 sparse capture exists (4607 selected IDs, partial inventory,
no self-drift); ACK17 counters remain unknown. Stable prefix counts and the
absence of a growth snapshot do not prove the absence of a leak.

## Preservation and ownership

`failure/manifest.json` SHA256:
`46ad1f9701c5e3bd000b7fb58e7c7d638a1c1bc580d376ea4c2df1f182b126f2`.
It covers244 exact copies,177 declared raw artifacts and the archived51 runtime
files/9 helpers. Command00–16 remain in raw storage with declared hashes; the
failure command17 is copied. The base packet is immutable.

`effective-native-supplement.json` additionally binds the executed native overlay
and the base manifest. The initial packet selected JSON/text and source files;
the actual overlay `.gd` requires this explicit supplement. Its SHA256 is
`de1838cf836e7dfd9a80fa05c7636774e43da0121dc3d7b551e02b90f5f746b1`.
`seal_s96.py --verify` checks both domains against retained originals.

The outer retained-handle observer captured supervisor6888, host22148 and
helper23452 exiting1; editor50100 and helper5652 exited2. Import29676 exited0.
Inner editor exit/capture remain missing; outer evidence supplements them
without converting a forced exit into natural success. Jobs reached zero and
closed; probes, process handles, sockets, threads and journal/index owners were
released. Scheduler state3/result1/no instances and absent known PIDs were
captured before task retirement at16:36:46 UTC. The deletion receipt remains
under the original S96 `launch-01`, after the failure packet was sealed.

## Repair boundaries

The Windows rename/retained-DELETE-handle hypothesis is being tested in a small
owned pinned-Godot probe, separately from the long coupled run. A reproduction
of that sharing state would establish a mechanism, not prove it caused S96.
No old run ID, partial sample, signature or Stop state may be reused as PASS.

A candidate START/ACK reader repair must retain the original deadlines and
heartbeat/status-gap measurements. Open-null can remain pending for another
frame; size, short-read, malformed/schema/hash/postcondition failures remain
fatal. Bound diagnostic output and preserve first failure/recovery observations.
The candidate needs real native regression evidence before another long run.

Current source/implementation status belongs only to the tools plan. The exact
previous S96 progress is `tools-plan-s96.txt`, hash in `plan-archive.json`, with
AUTHORITY=0. All S70–S96 failures and S93 latency/S86 ObjectDB questions remain.
