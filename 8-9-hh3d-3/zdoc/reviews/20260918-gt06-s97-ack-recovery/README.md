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

The owned pinned-Godot probe completed at16:47:24 UTC. A retained DELETE-access
handle after rename made the visible file unopenable: Win32 non-delete-sharing
open returned32 and Godot returned12. The same Godot process read the exact
40 bytes after holder release; a normal read-only holder did not block it.
Native25620/helper18964 and parent48464/helper43044 exited0 with clean Jobs and
handles. See the43-hash rename-probe-evidence.json inventory. This establishes
a mechanism, not the missing branch or interleaving of S96.
No old run ID, partial sample, signature or Stop state may be reused as PASS.

A candidate START/ACK reader repair must retain the original deadlines and
heartbeat/status-gap measurements. Open-null can remain pending for another
frame; size, short-read, malformed/schema/hash/postcondition failures remain
fatal. Bound diagnostic output and preserve first failure/recovery observations.
The candidate needs real native regression evidence before another long run.

Current source/implementation status belongs only to the tools plan. The exact
previous S96 progress is `tools-plan-s96.txt`, hash in `plan-archive.json`, with
AUTHORITY=0. All S70–S96 failures and S93 latency/S86 ObjectDB questions remain.

## Candidate validation (in progress)

The sole runtime delta is benchmark_native.gd, SHA256
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.
Existing affected Python regressions86/86, new binding4/4 and retained overlay6/6
passed under owned actual exit0 captures. Reader fixtures execute inherited
START/ACK methods on real files and the real adapter, while bypassing full boot
and stopping after one validated slot. They are not campaign or memory gates.

START malformed01 correctly rejected JSON with actual native/helper86. Its
first collector rejected the expected Godot parser diagnostic; original outer
target12764 exit1 and raw resultfalse remain. The strict metadata-only
revalidator checked exact bytes, source/stack binding, actual exits and cleanup;
target22088/helper532 exited0 and produced reader-start-malformed-revalidated-01.json
(SHA2561ef2b2e863efc8d312e91c5c07496cdd2b41080e4b2c0f3939ad1c3d494130cd).
No engine rerun occurred. Remaining cases use the revised driver and fresh IDs.
The prelaunch intermediate-pin rejection in reader-revalidation-owned-01
launched no child; wait for a writer stable handoff before taking a helper pin.

Use the current tools-plan markers for whether reader validation or a coupled
diagnostic is still active. A candidate/source change always requires a new
run identity. Old and new helper hashes remain separate in their freezes.
