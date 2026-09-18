# S81 campaign launch and initial observation

AUTHORITY=0. This is a dispatch/initial-progress checkpoint, not a full run,
benchmark acceptance, final evidence closure or critic verdict.

Source checkpoint: `b3862a1079196d26d21b25a84ae4edfe52f482e2`.
The earlier `checkpoint-paths.json` and `git-index-verification.json` describe
that exact checkpoint, including its then-current plan. Subsequent plan and
launch records do not alter those frozen hashes. To repeat the complete
inventory verifier, use that checkpoint's checkout; later plan bytes are
expected to differ. `git-source.json` independently verifies all51 runtime
files against HEAD/disk immediately before this launch.

Campaign: `gt06-s81-campaign-01`, launch1, run00 attempt01. Demand-only Windows
task: `\HHStudio.GT06.gt06-s81-campaign-01`, started2026-09-18T08:17:52Z.
Raw campaign and its sibling `-supervisor` remain under `studio/.local/reviews/`.
The fixed source closure is `e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`;
the profile is unchanged. Copies retain exact initial campaign/request/start
bytes, and the observation binds their originals by hash.

`scheduler-observation.json` records a separate live query at08:19:21Z:
state4, one instance. `observation.json` at08:20:09Z records host4132/editor48332
on the same run with empty stderr and the first completed warmup:62.000410s
joint,38.391522s HTTP,23.513928s native. Warmup1 was active. The first warmup
cannot establish stable throughput or an ETA for350 batches; journal I/O and
runtime costs can change as history grows. No full run has passed yet.

Keep source/profile/workstation unchanged. Do not run engines, tests or heavy
hash audits beside measurement. The existing heartbeat checks every15minutes;
use live scheduler state and a short log tail, not this historical observation,
when resuming. Preserve failures and Stop latches. Only verified complete runs
under unchanged inputs can be reused; partial S80 samples are excluded.

After terminal completion, verify the full10×35 dataset, all actual exits,
owned trees/handles, new child-terminal-cleanup records, source/artifact hashes
and every attempt. The draft S80 sealers must be adapted to this51-file source
and the new terminal record. Then two new independent critics must review the
same final closure before coordinator acceptance.
