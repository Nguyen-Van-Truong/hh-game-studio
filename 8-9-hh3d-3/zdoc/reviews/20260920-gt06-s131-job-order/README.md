# S131 Job ordering repair and retained RSS failure

Runtime checkpoint: `b8687415`; formal runtime53 closure:
`763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4`.
Profile and native workload are unchanged. This packet is diagnostic and
implementation validation; it is not GT06 acceptance or a final critic verdict.

The original code assigned the gated helper before configuring the CPU limit.
Windows adds accumulated member user time when setting a per-job time limit.
`probe_order.py` demonstrated this mechanism in four owned Python-only lanes:
configure-before-assign read back the exact original limit for both roles;
configure-after-assign included accumulated user time even after another Set.
See [Microsoft JOB_OBJECT_BASIC_LIMIT_INFORMATION documentation](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).

The repair configures the empty Job before assignment and keeps one strict
Set/Query comparison. Callback failure retains cleanup ownership. The unreleased
helper is killed and waited before an uncertain Job close. Limits were not raised.
`validation-01/summary.json` retains final-source 22 Job tests, 170 affected
benchmark tests, two actual Python success lanes and two injected rejection lanes.
Rejected configuration never launched the target; owned Jobs and handles closed.

S130 correction: the numeric +156250 was S126 reference data, not an observed
S129 value. S129 performed a successful Godot import but never started benchmark
workload. Its numeric readback is UNKNOWN. Previous plans are preserved byte-exact
in `archive/`, with hashes and AUTHORITY=0. The old packet remains immutable.

The subsequent coupled diagnostic completed six HTTP/native batches and failed
the original host RSS gate at batch5: 40,861,696 to 45,395,968 bytes (+11.0966%).
The last value is below batches0-2; this is a gate failure, not a proven leak.
The sibling `20260920-gt06-s131-rss-failure` packet preserves 101 files under manifest
`2bab12d6417a1b9cbf404f0fb786bacd2d0817e306b4d7fbb47a595d8c2d9ead`.
Actual launcher/host exit1 and import exit0 are retained; editor natural target
exit and observer self-exit remain UNKNOWN. Both benchmark Jobs were zero/closed.
The one-use task was retired after preservation (`scheduler-retired.json`).

Offline allocation replay reads that packet and reproduces each saved sample
exactly, three times. Both owned Python runs exited0 with native probe/Job cleanup.
The traced arm retained approximately66KB of traced Python allocations; its
tracking overhead makes working-set comparisons with the untraced arm unsuitable
for acceptance. The untraced arm plateaued around38.5MB working set after initial
allocation. These results concern released assembly graphs only; they do not
prove the original host journal/thread/private memory behavior or any root cause.
See each `memory-replay*/allocation-rows.json`, `probe-cleanup.json`, and owned
capture. Preserve the failed acceptance sample without subtracting overhead.
