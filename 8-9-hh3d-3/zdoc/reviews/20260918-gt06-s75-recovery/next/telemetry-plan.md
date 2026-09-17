# S75 bounded external telemetry preparation

Preparation only; no observer or campaign was launched here. Use the existing
`../owned_telemetry.py` helper unchanged. Its reviewed SHA256 is
`2fe8051e5e3a50ebdddfefb34aaa3fed5ee4e20341ca1f8ccb37ae05da12b0ef`;
verify its current bytes before use. The helper's self-test does not measure
overhead on a campaign and does not prove any prior failure's cause.

The coordinator can collect one disclosed supplemental window of at most 120
seconds, interval 1 second, on the next owned host/editor pair. Suggested
diagnostic ID: `gt06-s75-campaign-01-telemetry-01`. Keep telemetry outside the
campaign raw tree and source49 domain, under a fresh coordinator evidence
directory. Record observer invocation, source hash, wall/monotonic timestamps,
stdout JSONL, stderr, actual host exit and cleanup separately. Do not write a
fixed target PID or reuse S73 identities.

1. First confirm the coordinator's approved campaign/attempt, source49/profile
   and live ownership. Read its exact host-owner and editor-host process-start
   records and owner invocation paths. Cross-check the native `ready-00.json`
   run/source/profile/PID with the editor owner. Do not discover targets from
   a global name match or expand descendants. The only targets are that owned
   host Python and owned editor Godot; the observer has its own separate owner.
2. Obtain exact creation FILETIME ticks and full executable paths for those
   owned PIDs from retained ownership handles using read-only `GetProcessTimes`
   and `QueryFullProcessImageNameW`, or matching existing `windows:<integer>`
   probe identities. Confirm each executable against the pinned owner
   invocation. A rounded CIM/ISO timestamp is insufficient. If the required
   identities are not available yet, capture a small coordinator-owned
   read-only identity record for the already-authorized PIDs before sampling;
   no runtime source change is needed. Close every bootstrap handle.
3. Start the unchanged helper only after those identity records exist. Pass
   two explicit `--target PID FILETIME EXE` triples, `--duration 120 --interval 1`
   and the unique diagnostic ID, using pinned console Python with `-B`. The
   helper opens once, verifies creation ticks and image, retains the original
   handles and does not reopen by PID. A reuse/mismatch/access failure aborts
   sampling; do not elevate privileges or replace errors with zero.
4. Define t0 as the observer start after both owned identities are established;
   retain each target creation time and the delay to t0. This is the **first
   bounded observation window after identity**, not a claim to have sampled
   every instant of process startup. In particular, `joint-00.json` may not
   exist until batch0 ends; waiting for it must be disclosed and must not be
   described as first-startup telemetry. Do not delay/reset the benchmark or
   its baseline to wait for an observer.
5. Use the established separately bounded coordinator host wrapper. The helper
   has a cooperative 120-second deadline, not a hard API/output watchdog.
   Set a 150-second outer bound on the observer only. If the observer hangs,
   stop only its owned process/tree, capture that nonzero/incomplete outcome
   and its handle cleanup. Do not terminate, pause or reprioritize the sampled
   campaign to rescue telemetry. Keep polling/communication calls bounded.
6. Preserve every emitted API status. Require matching `start`/`identity`/`end`,
   independent actual exit, and successful closes for a complete diagnostic.
   Source schema/recorded result codes alone are not process-exit proof. Never
   turn a telemetry failure or absent metric into a successful measurement.

The intended command shape, with actual owned values substituted by the
coordinator, is:

```text
<pinned-python> -B <product>/zdoc/reviews/20260918-gt06-s75-recovery/owned_telemetry.py --run-id gt06-s75-campaign-01-telemetry-01 --target <owned-host-pid> <exact-host-filetime> <pinned-python> --target <owned-editor-pid> <exact-editor-filetime> <pinned-godot> --duration 120 --interval 1
```

The helper reads CPU priority class, memory priority, power-throttling masks,
current RSS, private commit, page-fault counts/deltas, handles, and global
physical availability/commit. The observer has real CPU/memory/I/O cost: retain
its duration and identity beside any associated measurement and disclose it
to critics. No concurrent tests, imports, full raw hashing or extra engines
should accompany an official measured campaign. This plan does not authorize
an undisclosed observer or change its eligibility rules.

Interpret RSS/private commit/fault movements only as correlation. Fault counts
do not distinguish hard faults, and priority masks do not identify the cause
of a trim or retained objects. Keep the existing current-RSS baseline, 110%
gate, non-RSS counter gates, 2s status limit, 500ms p95, workload, 5+30 batch
split and 7410s/run unchanged. The telemetry cannot reconstruct either failed
S73 attempt, substitute native ObjectDB/resource counters, remove failed
samples, or provide final native exit/Job cleanup proof.
