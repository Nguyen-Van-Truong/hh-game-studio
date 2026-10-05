# GT-06 formal08 closeout and bounded repair — 2026-09-29

AUTHORITY=0. GT-06 remains IN_PROGRESS; no accepted pair, dataset or critic
package. GT-07 stays unopened. This report supersedes the live status in the
formal08 dispatch note; it does not rewrite any original verdict or raw file.

## Verified outcome

`gt06-o4-formal-08` ended at 09:30:19 Asia/Saigon. The demand task is Ready,
has no running instance and returned 1. No campaign host or engine remains.
Original source: `d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475`.
Profile: `9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e`.

Pair 0 completed 35/35 batches. Before editing source, the coordinator verified
405 captured artifacts, source bindings, native assembly and owned captures.
Host 29164, editor 23212 and import 19300 have actual exit 0; their wrappers,
Job/tree/handle release and terminal cleanup verified. The bound run hash is
`29233a728fe6219567aa9a2a381ec8b99262804f953cb2c153eb920b076be7f1`.

Completion was **not** an O1 measurement PASS:

| Metric | Observed | O1 result |
| --- | --- | --- |
| Host private commit | Baseline 40,140,800; max 50,483,200 bytes | Above 110% baseline |
| Host private commit trend | Early max 46,374,912; late max 50,483,200 bytes | Above 105% early max |
| Editor handles | Baseline 558; early max 557; late/max 562 | Late exceeds early + 2 |
| Inspect / Stop p95 | 290.28137 / 88.07516 ms | Within 500 ms |
| Largest status gap, including warmup | 1880.6612 ms | Within 2000 ms |

Editor handles fluctuate; the spike is not proof of a monotonic leak. Host
handles, editor objects/resources and editor private commit meet the pair's
O1 rules. The full two-pair dataset does not exist.

Pair 1 completed 19 batches before its watchdog stopped it for CPU pressure.
Replaying the original policy reproduces CPU_PRESSURE at sample 477, after
64.172 seconds of sustained >95% system CPU. Its parent classification remains
INFRA_ABORT. Its outer Job is closed/zero and the owner handle is released;
natural host/editor exits and the child's terminal-cleanup receipt are absent
after that stop, so they are not inferred. Import exited 0. Scheduler exit 1
does not substitute for those missing child observations.

The campaign is incomplete **with a confirmed O1 failure in the completed first
pair**. The later CPU abort cannot erase that failure. September 29 has used
one of two daily INFRA_ABORT slots; an available slot is not a reason to rerun
the unchanged failing source. Formal06/07 remain PRODUCT_FAIL historically.

Raw is preserved at `studio/.local/reviews/gt06-o4-formal-08` and its supervisor
sibling. The sealed package `studio/.local/reviews/gt06-formal08-closeout-20260929`
contains an audit and a CRC/member-hash-verified ZIP of 788 files (266,280,839
uncompressed bytes). ZIP SHA256:
`d1c4dc2950a68fd472051342131cfe16877bbc05e9d922980a4e78ac6033a1d9`.
Manifest SHA256:
`faac979fcbaf03de3dd8d898baa90d459e1a08a62966bd87511e1fc97ec4bd0b`.
Audit SHA256:
`d83f2e8382934033fb589b7f5a2aca8314d9addcd361f8354c808b89e84c353d`.

## Repair and validation

The harness previously launched pair 1 after verifying pair 0's completeness
and cleanup without evaluating its final O1 windows. It now evaluates every
complete 35-batch pair before launching the next. A FAIL or GAP preserves the
raw, real exits, capture and hashed measurement summary, then stops with
CAMPAIGN_RUN_MEASUREMENTS_NOT_PASS. A complete pair recovered by the existing
read path is screened too. Acceptance still requires two fresh verified pairs;
the single-pair summary explicitly grants no campaign acceptance.

The calculation and validation routines are shared with the full dataset
verifier. Profile hash, all thresholds, warmup handling, timeouts, 35-batch
workload and two-pair dataset requirement are unchanged. Synthetic tests prove
FAIL/GAP prevent pair 1 while PASS reaches its launch, with raw evidence kept.
Reanalysis of original pair 0 returns exactly PRIVATE_COMMIT_GROWTH,
PRIVATE_COMMIT_TREND and RETAINED_COUNTER_GROWTH. This is a new analysis of old
raw, not a run executed on the repaired source.

The HTTP phase recorder also retained two large dictionaries per event after
its first lookup failure. In formal08 that capture occurred in batch 7, when
host private commit rose from 40,263,680 to 45,514,752 bytes. This correlation
does not explain all later growth. The repair stores immutable compact event
rows, shares them when freezing the failure window, and materializes detached
JSON dictionaries only for output. Both full 8,192-event windows, all fields,
timestamps, route counters and bounded unfinished spans remain available.

A separate Python allocation probe against source 03137461 observed:

| Python traced allocation | Before repair | After repair |
| --- | ---: | ---: |
| Added at first failure capture | 3,869,656 bytes | 67,072 bytes |
| Total after the live ring fully rolls over | 9,281,252 bytes | 4,167,612 bytes |

Both snapshots validate and retain 8,192 current and 8,192 failure events.
This proves reduced Python allocation in that controlled probe; it does not
prove OS private-commit compliance or solve editor handles. A regression also
checks the frozen pre-bind socket state survives rebinding, complete eviction
and caller mutation of returned snapshots.

215 focused tests passed with actual exit 0 in 45.640 seconds; no engine was
launched. The logged command and exit receipt are in
`studio/.local/reviews/gt06-pair-guard-20260929-01`. This count includes the
focused earlier tests and is not additive. `git diff --check` passes.

Candidate formal closure (54 files):
`8275722a4519ae435e5f69c23f9afdde1801dbf3873ba3ad4bb32c59d45e000f`.
Command-residency diagnostic closure (48 files):
`9eccd4530acd98e0f04cf8b565e5a6eb9e3a519e12c71ce17cb67b264bc3a570`.
These are new candidate closures, never rebound to formal08's raw.
The 63-member verify ZIP is CRC/member-hash checked; its tracked manifest is
`zdoc/reviews/20260929-gt06-pair-guard-manifest.json`. ZIP SHA256:
`e2f4da59eab3b12387ecf7dcf35e91d976d0ee3c2ef1d9196465fcfd4dcbda5e`.

## Next work and lessons

Use one fresh command-residency diagnostic to measure host memory after this
specific repair, including actual exit and ownership cleanup. Record whether
a lookup failure actually occurred; a run without it does not exercise the
failure-window allocation. Keep the 35-batch command mix and journal intact.
Do not call this a formal pair or proof of editor behavior.

`gt06-memory-diagnostic-05` was dispatched at 09:54:44 Asia/Saigon through
the demand-only task, with the 48-file closure above and fresh O4.1 preflight.
The preceding 60.437-second window observed CPU max 81.13354%, mean 48.68486%,
RAM minimum 6.95386 GiB, commit max 73.40952% and no foreign engine. This is
attempt 1 of the new compact-recorder diagnostic direction; do not modify its
source or start competing workloads while it runs. Prior residency04 took
75 minutes; that is an observation for scheduling, not a new timeout or ETA
guarantee. Raw is written under its own run ID without overwriting old runs.
The actual running child source list matches the frozen 48 files. The old
heartbeat ID could not be updated because it no longer exists; the app
confirmed creation of `ti-p-t-c-gt06-sau-diagnostic-b-nh`, every 30 minutes,
to continue this chat from the real run state and remain quiet when unchanged.

Editor-handle attribution remains open: prepare the O1.9 stock-editor control,
state workload equivalence and limitations explicitly, and never subtract
control counters from formal results. No debugger branch is reopened. Bound
this direction by O3's four hours/three attempts, then report options and move
to the allowed O2 fixture lane if unresolved. Do not dispatch formal09 merely
because the CPU cooled down; first review host growth and the editor trend.

Persist complete-pair measurement decisions as soon as they are available.
Treat exit 0 as lifecycle proof, not performance acceptance. Budget diagnostic
storage as measured process memory; retaining bounded data can still exceed
the gate. Preserve failed runs and distinguish a demonstrated allocation
improvement from an unproven whole-workload repair.

## Diagnostic05 closeout

`gt06-memory-diagnostic-05` ended after 27 complete command-only batches with
actual child exit 1 and `TERMINAL_TIMEOUT` in batch 27. The host Job was closed,
zero active descendants were observed, the wrapper handle was closed and not
retained, and cleanup recorded no cleanup errors. The final phase snapshot
validated with no unfinished spans and recorded a real first lookup failure.

The partial series is diagnostic only: baseline private commit from batches
2–4 was 32,964,608 bytes; the largest measured batch 5–26 value was 42,246,144
bytes (+28.156%). It recorded status gaps of 2,015.2852 ms at batch 7 and
2,046.7385 ms at batch 22. No editor or native Godot process was involved.
The raw package is
`studio/.local/reviews/gt06-memory05-closeout-20260929`; its 126-member ZIP is
CRC/member-hash verified with SHA256
`a14b065a57ca8a45d174e0f8bb53009a96d7377b4fea36c89505c863ed5f89b3`, and its
analysis SHA256 is
`a24b34d40b33a19ec23c5d205180e8565e31cfb783906e9f5897f311767bbb4b`.
The tracked package manifest is not an acceptance verdict.

The final timed lookup spent about 2.05 seconds in `client.headers`, while the
matching server lookup and journal snapshot held the journal guard for about
2.28 seconds. The journal was 26,436,349 bytes at batch 26. This establishes a
credible scaling boundary for the existing full-history verification path; it
does not prove a single root cause for all earlier private-commit growth. The
first-failure phase recorder was exercised, so the compact-row repair is not
the complete fix. Do not rerun unchanged formal09.

## O1.9 stock-editor control closeout

The first control attempt (`gt06-stock-editor-control-01`) stopped before
launch because the dispatch CPU counter reported a false-looking 100% series;
its raw remains separate and is not a product result. After the observation
window returned to normal, a fresh current-source control
`gt06-stock-editor-control-02` ran once with the benchmark and studio plugins
absent, no HTTP/native mutation cycles, and the same pinned Godot binary.

The control captured 2,809 external samples over 720 seconds. The target
editor's retained handle count was bounded and non-monotonic after startup:
554–577 (first post-startup sample 577, last 554). Its private commit in the
same window ranged from 813,891,584 to 892,125,184 bytes; these values are
descriptive control data and were not subtracted from formal measurements.
The editor exited with an independently observed exit code 0; the owned Job
was closed with zero active members, no taint, and no retained probe handle.
The dispatch preflight lasted 60.36 seconds (CPU max 80.0983%, mean 51.0494%,
available memory minimum 10,205,282,304 bytes, commit maximum 67.2157%, no
foreign engine). Raw ZIP/member hashes were verified; the tracked package
manifest is
`zdoc/reviews/20260929-gt06-stock-editor-control-02-package-manifest.json`,
with archive SHA256
`52e914f1481f43ea40df9ae9a3740e50ead9aac94b744ba3f0657ffe6870ddae`.

This stock run shows ordinary editor handle fluctuation of the same order as
the earlier idle control, so it does not attribute formal08's editor trend to
the benchmark plugin. It also does not prove that the plugin or host phase
recorder is safe under the full 35-batch workload. Formal08 remains O1 FAIL
for pair 0 and INFRA_ABORT for pair 1; no formal09 is dispatched, O1/O4 and
timeouts remain unchanged, and GT-07 remains unopened. The next bounded lane
is the O2 fixture work after this review, unless a separately justified source
repair is found.
