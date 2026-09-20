# S126 full stock diagnostic — Job readback boundary

`AUTHORITY=0`; diagnostic-only and excluded from F13/F14. The run was created
with a fresh ID and pinned to the S125 candidate source closure
`6d580e30e6d9368a5118749687589e4893fc5b88bcaf6b0af4414ce15ce91fc2`, the
unchanged profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`
and native hash
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.

The launcher stopped before the editor or native fixture started. The Job
readback requested `job_time=72000000000` (100 ns units), while Windows
reported `72000156250`; flags, active limit and memory matched. The original
strict check therefore raised `BENCHMARK_JOB_LIMIT_MISMATCH`. The owner Job
closed with `zero_observed=true`, wrapper exit `2`, and no retained handle;
the target has no exit because it was never started. This is a preserved
pre-engine failure, not a status-gap, handle-leak, or gameplay result.

The same Job readback failure is retained in S117's failed-launch packet. Do
not weaken the equality gate or rerun the 35-batch engine until a static
Windows readback attribution establishes whether the 156250-unit rounding is
an OS representation boundary. No S126 samples or post-failure snapshots are
eligible for the dataset. The full diagnostic helper remains here for a later
fresh ID only after that attribution; it uses the stock workload and captures
handles/PSS only after an original gate failure.

Selected raw artifacts are copied byte-for-byte beside this file. `manifest.json`
records their hashes and excludes the large local runtime tree, caches,
journals and secrets. `README-seed.md` is historical scaffolding and is not
part of the evidence set.
