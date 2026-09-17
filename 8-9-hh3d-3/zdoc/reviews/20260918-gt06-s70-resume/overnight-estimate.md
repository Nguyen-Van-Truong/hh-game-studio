# Campaign02 overnight duration estimate

One bounded read-only snapshot, approximately **2026-09-18 01:31:37–01:31:51
Asia/Saigon** (2026-09-17 18:31:37–18:31:51 UTC). No task action, Stop,
test/engine launch, source edit, polling loop or full raw-shard scan was used.
This is a workload-duration estimate, not an acceptance review or forecast of
successful completion.

## Observed state

Campaign `gt06-s70-campaign-02` has only `run-00-attempt-01` at the snapshot.
The attempt has published batch captures **00, 01 and 02**, plus their joint
observations and sample previews. These are **three warmup batches**: indices
0–4 are warmup, and indices 5–34 are measured. Therefore the observed progress
is **0/10 full runs, 0/300 measured batches**. The three batch captures do not
prove a completed/resumable run; that requires all 35 batches, actual exits,
cleanup and the verified run capture. There are 347 batch slots left across
the campaign, including the currently active warmup batch3.

The latest six host-tail lines report batch3, phase `commands`. The latest
eight native-tail lines report batch3/cycle0, `HOST_START`, with monotonic
timestamps advancing from 364064775 to 367965464 microseconds. This native
phase is consistent with waiting for the host command phase and bound start
permit; it is not, by itself, a stall. Both log files had write times around
18:31:51 UTC. The editor stderr is zero bytes, and the sampled host and
supervisor stderr tails were empty. No failure artifact appeared in the small
attempt-root listing, and the supervisor stdout tail was empty (full-run
completion has not happened). No genuine failing/stalled phase was established
by this snapshot. No scheduler status or process census was taken, so this is
progress observed at the recorded time, not a claim of continuing liveness.

The raw supervisor `start.json` records **2026-09-17T18:25:28.861415Z**, or
**September18 01:25:28.861415 +07**. Use that recorded date; earlier prose using
September18 UTC was one day different. The later-turn operator should bind
times to raw records, not copy the earlier narrative date.

## Small timing evidence

Each duration is `(host_window.ended_mono_us - host_window.started_mono_us) /
1e6` from the corresponding 2.3KB `joint-NN.json`. It covers host commands,
native cycles and the joint ACK boundary. It excludes startup before the first
host window, the short interbatch assembly gap, and final run/dataset assembly.
Filesystem times below corroborate wall-clock order; monotonic differences
are used for the rate calculation.

| Batch | Role | Host window, seconds | Capture write time, +07 | Joint SHA256 |
| --- | --- | ---: | --- | --- |
| 00 | Warmup | 58.200640 | 01:26:41 | `8bf7851f0d2d416559785e784211b2d57ada57560ac1636cece3169b6c4127ca` |
| 01 | Warmup | 64.919250 | 01:27:46 | `a42941876148e40d762e9f7f5156b495f9ba5423ccc6ceb837911ce5a6cda1b1` |
| 02 | Warmup | 181.935128 | 01:30:48 | `1eb5b53522b4c505c216df0767e49373312ba3a16b82340e5fd764605b4e033c` |

These hashes are the references published in the corresponding small
`batch-capture-NN.json`; this timing task did not independently revalidate
their larger command/native shards. All three joint observations bind host
PID48568/start `windows:134341431297699638` and editor PID34644/start
`windows:134341431363866855`, with the expected campaign/run ID and source
closure. Native ACK generation advances101→201→301. The observed 1000-command
and 100-cycle batch contract remains the source/profile contract; no reduced
workload was substituted for this estimate.

Source closure: 49 files,
`21a17b2a350160efb17950979adada0a2b3e12dbd95e12158833acbe9f233aa0`.
Profile SHA256:
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
Campaign SHA256:
`7aae14996dc3518808b84b0f319fbf83b86e26c396979196cadc99a14ad9ff53`.

## Projection and uncertainty

The arithmetic mean is **101.685006 seconds/batch**; median64.919250s;
slowest181.935128s. Three early warmup samples are not a stable distribution.
Batch2 was almost three times batch1, and this snapshot cannot assign a cause
or establish whether later batches will improve, plateau or grow slower.

Use the end of batch2, about01:30:48 +07, as the calculation origin. The table
charges a whole batch for current batch3, conservatively ignoring its elapsed
progress, and includes all ten runs' warmup work. It adds no undocumented
speedup between runs.

| Constant-rate scenario | Remaining32 batches of run00 | Remaining347 campaign batches | Approximate campaign finish, +07 |
| --- | ---: | ---: | --- |
| Median observed rate,64.919s | 34m37s | 6h15m | Sep18 07:46 |
| Mean of all three,101.685s | 54m14s | 9h48m | Sep18 11:19 |
| Slowest observed rate,181.935s | 1h37m02s | 17h32m | Sep18 19:03 |

These are **rate scenarios, not confidence bounds or an ETA promise**. A
useful planning statement at this snapshot is **about10 additional hours at
the early average, with a broad roughly6–18-hour scenario range**, plus
unmeasured startup/final-assembly costs. Nine future pair starts, interbatch
processing and final artifact hashing/assembly can add time. Failure, an
operator Stop, changing machine load, performance drift, source mismatch or
missing counters can terminate the campaign instead of yielding a result.
Do not claim it will finish before morning from these data.

The current run still lacks warmup baseline batch4; measured counter-growth
and latency behavior has not yet been established. One full run contains35
batches, and all ten fresh pairs must succeed before dataset-level measurement
PASS is even possible. No current partial prefix is acceptance evidence.

Unchanged safety bounds are7410seconds per run and24hours for the scheduled
campaign. The24-hour point is **Sep19 01:25:28 +07**, relative to the recorded
supervisor start (scheduler dispatch may differ slightly). A deadline is an
abort bound, not an expected completion time or permission to retry. If rate
degradation makes a bound likely, report it; do not stretch the profile.

## Later-turn use

The existing15-minute heartbeat can take another small snapshot at its next
scheduled run; this subtask created no additional monitor. Prefer completed
joint-window differences and the latest few progress lines. Do not rescan
large command/native shards just to estimate time, and do not restart completed
runs. Once a full35-batch run closes, its total wall time will be a much better
basis than these warmup observations. Treat advancing `HOST_START` heartbeats
with a host command phase as expected waiting unless the applicable phase or
wall deadline, explicit failure record, or independent stalled progress proves
otherwise. Follow `campaign-operations.md` for exact Stop and terminal cleanup;
a latched Stop must never become an automatic resume.
