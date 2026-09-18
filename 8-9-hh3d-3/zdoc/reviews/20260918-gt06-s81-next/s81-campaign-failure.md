# S81 campaign failure — retained counter growth

`AUTHORITY=0`. This is a failure record and diagnosis boundary, not GT-06
acceptance, not a critic verdict, and not permission to open GT-07.

## Frozen run

- source checkpoint: `b3862a10`
- runtime closure: `e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`
- profile: `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`
- campaign: `gt06-s81-campaign-01`, run `r00.a01`, launch 1
- terminal observation: `2026-09-18T08:48:56Z`
- raw roots: `studio/.local/reviews/gt06-s81-campaign-01` and its supervisor

The run captured five warmups and eleven measured batch captures before the
owned host stopped at batch 15. The host completed the 1,000-command HTTP
portion of each captured batch. This is a partial run; it cannot enter the
10-run dataset.

## Observed failure

At `joint-15.json`, the native ObjectDB count was `71130`, while the settled
baseline was `71128`. ResourceCache stayed `6`; host handle count stayed
`198`; editor handle count was `555` at the failing sample, below the baseline
sample of `565`. The failure was therefore the unchanged public counter gate,
not a rewritten threshold or a substituted private metric. The recorded code
was `CAMPAIGN_RETAINED_COUNTER_GROWTH`.

The child terminal cleanup record reports Job zero/closed, no retained wrapper
handles, no live drain threads, and no cleanup error. The editor native target
exit is absent (`TARGET_EXIT_NOT_RECORDED`); helper exit `2` is recorded as a
separate fact and is never treated as the native exit. The supervisor ended
with task state `3`, result `1`, and no remaining instance. These facts prove
cleanup of the owned failure path, not a successful campaign.

## Diagnosis boundary and next action

The +2 ObjectDB delta is not yet attributed. Earlier S77/S79 probes showed
Tree/TreeItem ownership as a source-supported hypothesis, while S81's
`resources=6` and stable handles do not identify which objects were retained.
Do not subtract the delta, raise the threshold, replace ObjectDB with RSS, or
claim an operating-system leak. Do not rerun launch 3 under the same source
until a bounded diagnostic identifies the owner and verifies the native-exit
capture path. Any fix must remain inside the benchmark fixture, preserve the
GT05-pinned transport bytes, and receive a new source closure and campaign.

## Evidence integrity

The raw campaign and supervisor directories remain immutable. Existing S80 and
earlier failure packages remain separate provenance domains. The S81 sealer and
functional map drafts are preparation only and must remain marked `NOT_FINAL`
until a complete 10×35 terminal run, final manifest, and two independent
critic `PASS/TICK=yes` records exist for one exact closure.
