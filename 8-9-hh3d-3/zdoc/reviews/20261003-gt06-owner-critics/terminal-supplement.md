# Formal25 terminal receipt — additive review candidate

The first reviews of final manifest `fb5770aaaa30aeec4c481947a185c28e2f0bb4a10dae34c05f9b7610215100e0`
returned Astra TICK=yes and Sol TICK=no. Sol correctly identified that the
sealed raw archives included the quiet-chain Scheduler receipt but omitted
Formal25's own terminal observation. Both original reports remain unchanged.

The original Formal25 status query was retained in the local Codex tool log:

- Call `call_EtRT8ybSdZeMXNYUUADmdmI8` at 2026-10-03T11:08:05.403Z invoked
  `campaign_task.ps1 -Command status -CampaignId gt06-o4-formal-25 -Mode campaign`.
- Actual command exit0 at 11:08:06.916Z returned the exact formal task,
  state3, LastTaskResult0, zero instances, launch1, and last-run time16:13:55
  Asia/Saigon. This precedes its retained task deletion at11:08:55.2305036Z.
- The request, launch PID51568, XML digest and output directory join the
  unchanged Formal25 supervisor evidence. This is the original recorded tool
  result, recovered after review; it is not a new Scheduler query or a result
  inferred from PID absence, deletion, return.json, or child exit codes.

Raw exact call/result records, their original log offsets/lengths/hashes, and a
derived JSON view live under
`studio/.local/reviews/gt06-f25-terminal-supplement-20261003-01`.
The original complete conversation log is private and not packaged. The verifier
compares only these two bounded slices in place against the original log. The
supplement ZIP contains the slices and binding artifacts, not unrelated chat.

The new review manifest is
`studio/.local/reviews/gt06-f25-final-review-20261003-02/manifest.json` with its
SHA256 sidecar. It binds the entire original final manifest plus this additive
receipt, verifier, negative tests and unchanged first-review reports. The
original three archives, source domains, raw results, gates, successful pairs,
functional and repair/replay lanes remain unchanged. No benchmark or engine rerun
is needed to fix this archival omission.

Read-only verification from repository root:

```powershell
python -B '8-9-hh3d-3/zdoc/reviews/20261003-gt06-owner-critics/verify_terminal_supplement.py'
```

Both independent reviewers must review the new manifest and this correction,
keep their original reports verbatim, and write fresh second reports with an
explicit verdict tied to the new final hash. Earlier TICK=yes is not reused as
the new signature. GT06 remains IN_PROGRESS until both reviews and coordinator
checks succeed. Scheduler0 still does not replace actual role/Job/handle proof.

Future closeout must persist the exact terminal status query before removing a
task. The missing archive member is a packaging defect; do not respond by
repeating an already successful engine workload.
