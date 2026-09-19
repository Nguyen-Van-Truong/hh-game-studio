# S103 status-gap prefix

This is a diagnostic harness for the missing native `save_scene()` return
boundary from S102. It is pinned to the unchanged source checkpoint
`56bfd448e83aa2512c0c2561e8e1a29f12134360`, the 53-file closure
`7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`, and the
unchanged profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
The native base is `13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.

`prefix_probe.py` is inert on import. It verifies all 53 live source bytes,
generates the additive `native_probe.py` overlay in memory, and prints a plan
for exactly one preflight (1000 HTTP commands plus 100 native cycles) followed
by a bounded prefix of batches 0 through 6. The generated plugin belongs in a
fresh evidence project only; never edit `studio/tests/replay/benchmark_native.gd`
or the immutable S102 failure packet. The prefix keeps the production 2000 ms
status-gap threshold and all 35-batch profile constants. It is
`formal_acceptance=false`, `eligible_for_dataset=false`, and cannot open a
formal campaign or change a gate.

Static check, with no Godot process, scheduler task, or engine launch:

```powershell
Set-Location D:\dataDiskD\intellji\hoanhaosocial\hoanhaonew-20-6-2025\hh-game-studio
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s103-status-gap/prefix_probe.py --check
python -m py_compile 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s103-status-gap/prefix_probe.py
```

The future owned launch is one command after static review, using a new run
ID and a new empty root; no retry may reuse a failed root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s103-status-gap/prefix_probe.py --run-id gt06-s103-prefix-01
```

That command currently prints the frozen plan only. A coordinator may wire the
printed plan to the existing owned host/editor runner after review. The actual
runner must create the project, install the generated overlay, run one bounded
preflight, then run batches 0–6 with the original host/editor pair and fixed
workload. Stop after the first observed gap above 2000 ms or after batch 6;
never extend to a full 35-batch campaign from this diagnostic harness.

Cleanup is evidence-producing and identity-bound: request Stop through the
runner, drain and close the owned Job/process handles, capture actual target and
helper exits, verify the tree is zero, and preserve stdout/stderr and all
partial artifacts. Do not infer an exit from scheduler state, a wrapper code,
PID disappearance, or PID reuse. Do not signal a reused PID, delete the S102
failure packet, or overwrite a prior prefix root. Missing boundary rows remain
`UNKNOWN`; they do not become a latency pass.

No engine was launched while preparing this packet. The prefix remains
diagnostic evidence and requires fresh independent review before any status
decision.
