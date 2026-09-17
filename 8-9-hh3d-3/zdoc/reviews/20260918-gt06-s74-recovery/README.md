# S74 recovery: two failed conditions, unchanged S73 source

GT06 remains in progress. S73 launch1 terminated after1131.563 seconds with
`CAMPAIGN_RSS_GROWTH` at batch5. Five warmups and one failed measured capture
are retained; there is no completed run. Host RSS rose18,939,904→23,056,384
bytes (+21.734%). The same measured sample independently recorded2010.742ms
command response gap against the unchanged2000ms limit. RSS screening raised
first. Neither condition is waived.

`failure/README.md` and its manifest preserve239 raw hashes,64 exact copies,
36 batch references and30 absent Stop latches. Manifest SHA256:
`4fc4277d5514c8f4c411559091e5e2d83d4dd7bf5dfab1a5d0ffe9865ec86598`.
The host actual exit is1; the editor native exit is absent and wrapper2 does
not replace it. Both Jobs are observed zero/closed and wrapper handles released.
The separately captured terminal scheduler reports state3/result1/no instances.

`memory-diagnosis.md` found no RSS field, ABI-width, baseline or arithmetic
defect. Host working set changed strongly across the idle native interval;
this alone does not identify a leak, memory pressure or an external trimming
caller. Batch5 command time grew5.97× while journal size grew only20.06%.
`windows-memory-research.md` contains primary references and diagnostic limits.
In particular, WPR Reference Set would empty system-wide working sets and is
unsuitable here; private/peak counters cannot replace the declared RSS metric.

The coordinator performed read-only workstation observations after failure.
At one instant commit was49,851,535,360 bytes on roughly34GB physical memory,
available memory5661MiB, and Memory Compression occupied about4.22GiB.
No named common memory-cleaner process was found; WPR reported not recording.
These transient observations do not prove what caused the earlier failure.
No unrelated process, system setting, working-set bound or memory priority was
modified.

`residency_probe.py` is a bounded supplemental self-process diagnostic:32MiB
allocation,5 seconds touching each page,90 seconds idle,5 seconds waking the
same pages. `residency-01/` captures actual PID16692 exit0, wrapper exit0 and
clean owned tree. Working set stayed approximately49.45–49.51MB during idle;
private usage remained approximately42.08–42.19MB. Only11 additional faults
were observed after the initial active phase. It did **not** reproduce a large
residency drop. It neither certifies the Godot/HTTP workload nor repairs the
two failed conditions. The script uses only its own pseudo-handle and does not
launch tracing or change memory controls.

Decision: retain source `cb4d1f6f` and profile unchanged. A single new bounded
attempt under the existing campaign is justified for renewed observation after
the diagnostic, not as proof of a fixed root cause. The recorded terminal
cleanup, exact49-file binding and absent Stop latches satisfy structural resume
requirements. Use unused launch2; its run00 attempt2 has a new process pair and
starts a whole35-batch run. Prior failed data remains separately inventoried.
Do not infer a PASS from this decision. If the same failures recur, investigate
the owned scheduler process priorities and commit/fault behavior before another
retry; do not blindly dispatch launch3 or weaken the fixed gates.

Resume follow-up: recovery checkpoint `82f62a71`; launch2 requested at
`2026-09-17T21:40:37Z`. Separate live scheduler query and bounded tails at
`21:41:53Z` showed state4/one instance and matching host/native run a02
progress, native PID8776, empty stderr. `launch-02/observation.json` binds the
static launch/context/source copies and distinguishes startup from acceptance.
The existing15-minute heartbeat now uses launch2 and its supervisor directory;
`launch-02/overnight-schedule.json` retains the readback. Source remains the
unchanged49-file S73 closure. No benchmark result or root-cause repair is claimed.
