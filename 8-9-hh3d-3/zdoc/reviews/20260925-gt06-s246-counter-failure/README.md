# S247 — S246 formal counter failure

Fresh campaign `gt06-s246-formal-01` reached eight captured batches (`joint-00` through `joint-07`) and terminated in `joint_observation` at batch 7 with the unchanged `CAMPAIGN_RETAINED_COUNTER_GROWTH` screen. The editor held-handle row was 558 at the frozen baseline (batch 4) and 559 at batch 7. This is a gate-row diagnostic only; it makes no leak, ownership, or root-cause claim.

Import exited 0 with a closed zero-count Job. Cleanup closed the editor owner Job and released handles, but the editor target actual exit was not recorded; cleanup exit code 2 is not a natural-exit proof. Host/editor/supervisor scheduler state is not used as exit proof. No batches are accepted or merged.

Raw entries: 267; raw manifest SHA256: `e3e4be50cde3e0fcbe43958efa9ed462eae6984999e06f2e7b71e4dca733ecbe`; archive SHA256: `8c11df0104dd6da3bb404117cb2e01da672cc9d4e85db624726e88a8f5c02635`. Authority 0, formal acceptance false. Keep timeout, baseline, profile, counter, RSS, and the 10 fresh pairs × 35 batches gate unchanged. Do not reuse the campaign ID or retry the same counter hypothesis without a distinct supported boundary or owner ADR.
