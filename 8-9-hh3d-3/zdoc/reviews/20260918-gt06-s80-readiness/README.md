# S80: deterministic editor startup readiness

AUTHORITY=0. Supplemental implementation evidence; GT-06 remains unaccepted.

Source checkpoint: `f75a5d08422e5163c638b26de718126cf4c29cf3`.
Actual 50-file campaign source closure:
`1dc889ef923dee9b53c6faeeb1d6fd781acc3a89a4b860b531b55fc3a124cf8f`.
`campaign-closure-binding.json` corrects the preflight map: the original
`verification.json` queried dynamic imports before loading the trusted fixture,
so its 47-file digest `97b85f38c877854ebe4b869b119a0d7b7c6f24e62637540e4d31537c4e6815f6`
is a subset, not the full campaign closure. All 47 hashes match; the three
additional fixture modules also match source commit f75a5d08. No source changed
and no engine was rerun. Raw/copy hash inventories remain intact. Profile hash remains
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

The S79 focus probe observed two absent dialog Tree roots, then two blank roots
and exactly four additional Objects after a synthetic application-focus-in.
A second stimulus replaced both roots, invalidated their former IDs and retained
the same object count. This is a same-process causal mechanism, not retrospective
attribution of S77/S78, a real OS-focus test, or evidence of a completed campaign.

S80 dispatches one explicitly synthetic focus notification during startup,
before the existing four-frame/1.1-second settling interval and batch zero.
It verifies the pinned native callbacks, both blank dialog roots, source hashes,
scene identity/revision/bytes and notification delivery. The aggregate native
index advances to 1.3.0 with a closed readiness receipt. Input/batch schemas,
performance profile, five warmup and thirty measured batches, counter thresholds
and deadlines are unchanged. No private Tree mutation, counter subtraction,
focus grabbing, extra warmup batches, or fallback is introduced.

Validation:

- `checks-01`: 96/96, actual target36424/helper27660 exit0, tree verified.
- `checks-02`: 11/11, actual target31304/helper33644 exit0, tree verified.
  Only `test_native_benchmark.py` changed after the first lane: two additional
  regressions. All runtime dependencies match; this is 98 distinct tests,
  not 107. The second frozen snapshot is current.
- `gt06-s80-native-01`: import12460/native37788 actual0; one real semantic
  create/undo/save/reload cycle, clean logs, closed/empty Jobs. Exactly one
  setup dispatch and observation, 157 frames/1,107,642 microseconds between
  immediate and settled readbacks. Owned target26452/helper48868 also exit0.
- `gt06-s80-no-focus-01`: generated disposable driver deliberately omits the
  notification. Native19752 actual86, `BENCHMARK_STARTUP_NOTIFICATION_READBACK`
  in INITIALIZE, before batch/cycle0; no mutation, scene unchanged, logs clean,
  Job empty/closed. The first collector exited1 because it incorrectly expected
  the success-only `capture.actual_process_exit` field. Its helper/source/logs
  remain intact. Fixed `--verify-only` rechecks the original hashed
  `process-start.json`/`process-exit.json`; actual86 and wrapper86 remain
  separate records. **The engine was not rerun.**

The completed seven S79 service/GUI lanes and S69 managed replay are reused only
under the exact dependency bridge in `../20260918-gt06-s79-diagnosis/`.
Broad historical snapshots are not relabeled as current closures. Preflight
worker review is supplemental, not either of the two required final critics.

Next: a new full campaign, ten fresh host/editor pairs with all 35 batches per
pair. Prior failed/partial campaigns remain excluded. Final acceptance still
needs full evidence assembly and two independent PASS/TICK=yes reviews on the
same final manifest. GT-07 remains closed until then.

Lessons: load the trusted fixture before taking the dynamic imported-module
closure; verify the campaign's actual map rather than assuming preflight loaded
every dependency. Freeze edits explicitly before dispatch; a late test-only change needs
only its affected lane reminted. Read process-exit artifacts for nonzero native
exits instead of inventing success-only fields. Repair collectors against valid
raw evidence before considering another engine run.
