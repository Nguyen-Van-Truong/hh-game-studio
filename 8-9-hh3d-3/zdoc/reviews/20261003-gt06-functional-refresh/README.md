# GT06 review candidate after Formal25

Coordinator status: GT06 is not ACCEPTED. This packet joins the completed
Formal25 benchmark with current HTTP/UI/adversary lanes and authenticated
managed repair/replay. It is ready for review only when the final manifest's
byte and required-member verification succeeds. It does not prove a complete
authored game, Android exports, GT07–10 or human playtest.

## Owner handoff

Send this directory and the local final-review manifest to two independent
read-only reviewers using different models. Both must use the same SHA256 from
`studio/.local/reviews/gt06-f25-final-review-20261003-01/manifest.sha256`.
Do not substitute the benchmark64 hash for this combined review manifest hash.
Keep both complete reports verbatim, with reviewed manifest/source/profile/
dataset hashes, findings and explicit `TICK=yes` or `TICK=no`. Coordinator
rechecks unchanged bytes before deciding acceptance. No signature is supplied
by the preparer or scoped implementation audits.

1. Read `requirements.md`: F01–F15, TQ00/TQ06 and TX02/05/13, with exact limits.
2. Read the final `manifest.json`, its source/public-raw mapping and three archive
   hashes. Native execution217, benchmark64, functional driver73 and managed
   driver77 have different declared scopes. Historical S65/GT05 keep theirs.
3. Check real host, import/runtime/editor exits, identity, Job/tree/handles and
   no stale capture. Three intentional Stop runtimes retain UNKNOWN natural
   exits and wrapper2; clean cancellation is not natural exit0.
4. Review original fault → authenticated command → selected/reopened/readback
   script → COMMITTED/ACK → immutable replay, including retained nested flags.
5. Review full test invocations, actual exits, skipped cases and retained failed
   harness attempts. Verify source changes are confined to their declared domains.
6. Review original Formal25 two×35 samples/profile and O7 prerequisite; do not
   splice older campaigns, rerun engines or weaken gates for this review.

## Commands from repository root

Byte/coverage verification, no engine:

```powershell
python -B '8-9-hh3d-3/zdoc/reviews/20261003-gt06-functional-refresh/build_review.py' --verify
```

Existing semantic verifiers, no engine replay:

```powershell
python -B '8-9-hh3d-3/studio/.local/reviews/gt06-o4-formal-25-critic-package/verify.py' --studio '8-9-hh3d-3/studio'
python -B '8-9-hh3d-3/zdoc/reviews/20261003-gt06-functional-refresh/run_refresh.py' --verify-existing
python -B '8-9-hh3d-3/zdoc/reviews/20261003-gt06-functional-refresh/run_managed.py' --lane repair --verify-existing
python -B '8-9-hh3d-3/zdoc/reviews/20261003-gt06-functional-refresh/run_managed.py' --lane replay --verify-existing
```

These functional verifiers recheck/collect already completed artifacts; they
never launch an engine. They use retained original workstation paths, including
historical input anchors. Keep raw in place. The public ZIP is an indexed review
copy, not a relocated executable installation. Do not execute `--run`, recreate
old IDs, alter source/evidence, or overwrite an archive to make verification pass.

The final archive deliberately excludes private owner stores, live credentials
and caches. Public repair `journal.json` and `events.json` are hash-bound receipts
and remain included. The original private storage remains on the workstation;
it is not required to replay the public artifact checks. Integrity verification
does not replace semantic review, source audit or either independent critic.
