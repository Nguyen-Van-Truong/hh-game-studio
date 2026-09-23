# GT06 S212 terminal package

Authority=0 failed formal campaign packet for `gt06-s208-formal-01`. Run 00 completed 35 batches but was not accepted; run 01 completed batches 0–19 and failed in batch 20 with `ADMISSION_UNKNOWN`. The client timed out while reading the commands response, while the sealed journal retained the same command ID/digest as queued and then committed. This is retained as response-loss admission evidence; it does not prove a root cause or a leak.

Raw and supervisor files are sealed by the raw manifest and archive listed in `terminal-seal.json`. Cleanup evidence is retained; scheduler state or missing editor exit is not treated as natural-exit proof. No partial batches are merged, and no GT06 gate, timeout, baseline, profile, counter, or RSS policy changed. A future source repair must preserve same-ID lookup/reconcile semantics and use a fresh campaign ID.
