# S230 — S229 retained-counter formal failure

`gt06-s229-formal-01` was a fresh formal campaign after the S228
phase-correlated RSS boundary. It reached batches 0–16 (17 captured batches)
in run-00/attempt-01 and stopped during batch 16 joint observation with
`CAMPAIGN_RETAINED_COUNTER_GROWTH`.

The frozen formal screen used batch 4 as its baseline. Editor ObjectDB was
71128 at the baseline and 71130 at batch 16; resources stayed at 6 and held
handles stayed at 554 between batches 15 and 16. The editor RSS at those rows
was 129073152 and 182489088 bytes. The receipt is a gate-row observation only:
it does not prove a leak owner, measurement defect, or root cause.

Terminal evidence is sealed before any follow-up. The host wrapper recorded
actual exit 1, the import target recorded actual exit 0, and the editor target
exit was not independently recorded. Host/editor/import Jobs were zero and
closed, wrapper and probe handles were released, and the owner was closed.
Natural editor exit is not inferred from cleanup or scheduler state.

Authority remains 0 and `formal_acceptance` is false. Partial batches are not
merged into the dataset. The 10 fresh-pair × 35-batch gate, timeout, baseline,
profile, retained-counter and RSS policies remain unchanged; GT07–GT10 remain
unopened. The next valid work is a read-only review or a distinct supported
object-counter boundary before another fresh formal ID.

Raw evidence is retained at
`studio/.local/reviews/gt06-s229-formal-01` and the scheduler receipt at
`studio/.local/reviews/gt06-s229-formal-01-supervisor`.

- Raw manifest SHA-256: `30f0bba3ba413754d8055db62ecf1de36e1c6b43b547a99a8bb31ab393df949f`
- Sealed archive SHA-256: `391f0e6347f1fd1112366144b00622ac5d895ba669ad81a718e6918a4e29c92b`
- Archive members: 340

Run `python -B zdoc/reviews/20260924-gt06-s229-formal-campaign/verify.py`
for engine-free verification.
