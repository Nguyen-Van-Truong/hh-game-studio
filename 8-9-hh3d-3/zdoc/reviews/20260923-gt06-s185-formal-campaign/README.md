# S185 formal — sealed terminal failure

Authority is 0 and formal acceptance is false. The fresh stock campaign `gt06-s185-formal-01` used source checkpoint `f0e669f8`, source closure `fc46cfd2e80e8d78024b6a31c6c72be64f33d83aab4fe1abebaf899907f0e205`, execution closure `493a7ccce3e42993399910b0fe977f25448f411b863e4cca7b57904348ac374e`, and unchanged profile hash `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

The run completed batches 0–4 and failed in batch 5 `joint_observation` with `CAMPAIGN_RETAINED_COUNTER_GROWTH`. The wrapper then returned `BENCHMARK_WRAPPER_EXIT`; the raw child and parent records are retained. Cleanup records show owned tree zero, owner closed, no cleanup error, and the import process actual exit 0. Scheduler status and process absence are not used as natural-exit proof; any unknown target exit remains unknown.

Raw and supervisor files are retained in the local archive named by `terminal-seal.json` and are listed by the raw manifest. The archive is not an accepted benchmark result and does not establish a leak or root cause. No old partial run is combined with this attempt. GT06 remains in progress with zero accepted full runs; GT07–GT10 remain unopened.

Next action is read-only attribution of batch 0–5 counter deltas, child failure and cleanup from the sealed raw. Repair only a proven source or harness boundary. Do not rerun this unchanged source/hypothesis, alter gate/timeout/profile/baseline/RSS, or infer PASS from the scheduler.
