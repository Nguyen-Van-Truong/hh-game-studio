# S84 compact full-sequence attribution

AUTHORITY=0. Diagnostic only; never an eligible campaign sample or final review.

This continues the S82 investigation with a smaller collector, after the S84
original/sham/compact memory-cost experiment and controlled native growth/removal
proof. The base 51-file runtime and benchmark profile remain unchanged. The
copied editor plugin has a separately hashed overlay. Do not treat the official
source closure as the effective source of this instrumented run.

The collector retains ID/class pairs and exact-class Tree/RichTextLabel summaries.
It emits descriptions of newly reachable objects and records removed IDs/classes,
validity and per-Tree item counts. It cannot recover ordinary baseline content
changes, old per-item ownership, or the roughly 43,000 unvisited ObjectDB entries.
Counts alone do not identify a leak. The native controlled test proved the
diagnostic Tree and TreeItem are added, described and removed; residual ObjectDB
changes outside the inventory remained explicit.

Original census cost increased RSS by 117,919,744 bytes in the short intervention;
compact increased it by 2,412,544 bytes; sham changed it by -221,184 bytes. These
are single short comparisons, not a performance distribution or a claim that all
S82's 122,851,328-byte increase came from the probe. Original native exited0 but
its outer collector exited1 at an overstrict count assertion; that failure is
preserved and the comparison is derived from existing raw observations. There
was no engine rerun merely to change the collector result.

The runner still calls the unchanged campaign child and screen_sample, including
all 35 batches, 1000 HTTP commands and 100 native cycles per batch. Census occurs
at ACK4 and positive ObjectDB growth. All RSS, retained-counter, status, deadline,
Stop and process-owner checks stay active. The run is ineligible for acceptance
because it adds instrumentation and has no campaign assembly.

Fixed entries (run each only once, never overwrite an output ID):

```powershell
python -B zdoc/reviews/20260918-gt06-s84-attribution/diagnose_sequence.py --preflight
```

Then the coordinator launches the same file's `--supervisor` with pythonw and
`Start-Process -WindowStyle Hidden`. It creates only its own checked Job tree.
Read child/supervisor terminal files and actual host/helper/native exits; a
supervisor-return JSON is not an independently captured supervisor process exit.
Query current liveness before treating historical launch records as RUNNING.

Raw directories are `studio/.local/reviews/gt06-s84-attribution-preflight-01`
and `studio/.local/reviews/gt06-s84-attribution-01`. Preflight native54548 exited0,
wrapper0, Job zero/closed, stderr empty; this proves import only. The useful first
checkpoint is ACK4; previous sequence batches took roughly 1–2 minutes each.
One diagnostic may take approximately 45–75 minutes, with a hard 7410-second
limit. Neither reproduction time nor an ETA for the entire tools plan is known.

Hashes: base runtime e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f;
profile 0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85;
runner dacfc91721eefacc3be6f420e3812f320ad8a9a3f08ff7beafa0ea56d3b0f7c0;
collector 20ed7e62658c247265a8165024682efac78ae9c475a810bb6368e8fe9c75dd40;
effective copied native08afdefc7baafc2b581b2763d48eedecadfa32168f483a42b730ae42d11c0783.
