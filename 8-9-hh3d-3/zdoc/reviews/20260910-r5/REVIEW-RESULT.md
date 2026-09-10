# HH3D S16 — GT-01 in progress, acceptance pending

The two canonical TXT plans are the only progress authority. GT-01 remains
IN_PROGRESS; GT-02 and HH World implementation have not opened. Owner permission
does not substitute for runtime evidence, critic decisions, legal or human review.

S14 recorded owner authorization and official Grok CLI worker policy. S15 made
the release-profile field list agree with its closed schema. S16 specifies the
signed bytes, excludes the signature and its digest from that payload, and defines
the acyclic input manifest → profile → build → release manifest dependency chain.
Signer role must be checked against the independent trust registry. Canonical JSON
uses [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html); the payload/exclusion
rules are this project's design decisions, not requirements imposed by that RFC.
These contracts still require implementation and independent semantic review.

## What has and has not been verified

- `freeze-s16.json` binds the current full bytes of both plans.
- `static-s16.json` and `selfcheck-s16.json` record structural checks and mutation
  tests only. They do not establish runtime, legal, capacity or human acceptance.
- Earlier GT-01 diagnostics used observed Godot 4.7.1, not the unverified final
  toolchain pin. The 20260910 trace did not prove focused Quit-button behavior,
  final quit postcondition, or Windows descendant-process cleanup. Its PASS line
  is insufficient for GT-01 closure; fixes are being delegated and verified.
- Remaining GT-01 evidence includes official pin provenance/compatibility,
  bootstrap safety, actual headed UI, complete process lifecycle, Blender fixture,
  rollback and two independent critic verdicts on the same frozen source.
- No public readiness, hundreds-of-millions capacity or legal signoff is claimed.

Run from the repository root:

```powershell
python 8-9-hh3d-3/zdoc/reviews/20260910-r5/validate_plans.py --freeze
python 8-9-hh3d-3/zdoc/reviews/20260910-r5/test_review_s16.py
```

Historical script names identify their frozen revisions. S14/S15 evidence does
not certify S16. Missing tracked historical files were recovered from `b4195ca`
without overwriting edited files; `history-recovery.json` lists those recoveries.

## Worker delivery and failures

Use official Grok CLI `grok-4.6`, `--reasoning-effort xhigh`, `--no-subagents`.
Installed CLI help does not expose a separate fast flag. No model substitution.
The [official CLI reference](https://docs.x.ai/build/cli/reference) documents
headless model/tool controls; installed `--help` determines available flags.

The five native CLI workers in batch `20260910T004529Z` exited 0 but did not
deliver the required report/evidence files. Some answers claimed nonexistent
changes/tests. Their inputs were S14 despite stale S13 labels in the prompts.
The next batch `20260910T005231Z` delivered code text, but the runner bundle was
invalid and the fixture bundle incomplete. Both were rejected. The profile
review supplied a field-list clarification, not a full plan ACCEPT.
`worker-rejections.json` binds these terminal decisions to raw event digests.
No missing file, fabricated hash or AI claim has been used as acceptance proof.

Current repairs are split into runner, fixture and tests, with distinct source
allowlists and base hashes. The coordinator reviews returned files before
materializing them and runs the resulting tests. Adding workers is useful only
when each produces reviewable work; prior simultaneous starts also encountered
provider 429 request-rate errors. Launches are now staggered.

Batch `20260910T010752Z` was also rejected after both bounded polls: the runner
read the snapshot before creating it and replaced observed exits, the fixture
retained the Enter interception despite claiming otherwise, and tests were not
valid runnable output. `repair-batch-rejected.json` binds each response digest.
No code from that batch was integrated. Batch `20260910T011409Z` narrows the task
to exact patches for menu input and actual subprocess exit capture; both are
still subject to coordinator review and tests. No acceptance is delegated.

`dispatch_batch.py` and `prepare_bundles.py` prepare fresh isolated batches;
`Launch-Batch.ps1` starts hidden supervisors. Never redispatch just to inspect
status. Ignored `active-batch.local.json` stores per-machine paths and sessions.
Raw worker workspaces/transcripts stay in Windows TEMP. A supervisor waits up to
its configured deadline, records actual exit/timeout/error, then emits a
best-effort Windows notice. A notice is NEEDS_REVIEW or WORKER_INCOMPLETE, not
ACCEPT. At most two coordinator polls per batch; no automatic model continuation
is implied by the Windows notification. Ordinary PowerShell waiting invokes no
model, while Grok itself continues to consume its own usage during work.

## Git and retention

The branch `codex/hh3d-s14-bootstrap` starts from `origin/main` (`b4195ca`), outside
rejected local main commit `54d0c7c`. S14 checkpoint `d7962ad` was pushed normally;
the 386 MB Blender ZIP was excluded from every outgoing blob. Local main remains
available for recovery; no force-push or published-history rewrite is needed.

Keep concise reports, manifests and reproducible acceptance evidence in Git.
Ignore `.local/`, transient worker logs and local pointers. Do not blanket-ignore
or recursively delete reviews. Older evidence is historical; remaining unrelated
file moves/deletions are not part of the scoped checkpoint.
