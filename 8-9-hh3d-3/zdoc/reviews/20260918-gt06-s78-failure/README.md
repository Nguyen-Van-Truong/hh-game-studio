# GT-06 S78 campaign failure

This package records the first S78 full-campaign attempt without copying or deleting the raw capture. It is diagnostic evidence only; it is not a PASS and does not authorize GT-07.

Campaign gt06-s78-campaign-01, run gt06-s78-campaign-01.r00.a01, used source closure 649bd0f3e9a6a0a6d2249d952ec63f0dc6e29b2da3f273bd2b3ef8c8d169b18e and profile 0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85. It failed at the post-batch observation after batch 12 with CAMPAIGN_RETAINED_COUNTER_GROWTH; the editor ObjectDB counter was 71124 at baseline and 71128 at failure. Resources stayed at 6. The status gap was 550.192 ms for batch 12 and the maximum observed gap was 783.600 ms, below the 2000 ms gate.

The failure was retained with actual host exit 1 and import-host exit 0. The parent recorded owned-tree zero, owner closed, and no cleanup error. The scheduler result and wrapper exit are kept separate from these process records. No partial samples are promoted to a dataset and no retry is launched from this package. The raw source is studio/.local/reviews/gt06-s78-campaign-01/; this package stores only bounded summaries and exact hashes.

The evidence does not identify the object owner or prove a leak/root cause. S77 diagnostic03 remains supplemental and cannot waive the full benchmark. Before any future campaign, run a bounded diagnostic that distinguishes the editor counter delta and its owner under the unchanged source/profile/workstation; do not change thresholds or launch blindly.

## S79 correction

The original summary below is historical and has metric-label errors. Use
`../20260918-gt06-s79-diagnosis/failure-audit.md` and its JSON for corrected
reconstruction: baseline is batch 4 (565 editor handles); batch 12 assembled
status gap is 627.6519 ms (550.192 ms is only the native ACK component).
There are 13 raw batches, five warmup/eight measured, and zero complete runs.
Godot editor actual exit is unrecorded; wrapper 2 does not supply it.
Scheduler state 3/result 1/no instances at 06:15:55Z is a separate observation.
Original raw evidence and the original failure-summary.json remain unchanged.
