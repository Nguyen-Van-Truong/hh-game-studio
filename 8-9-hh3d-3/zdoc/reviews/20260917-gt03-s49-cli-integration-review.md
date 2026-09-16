# S49 CLI Job integration review

AUTHORITY=0
SCOPE=bounded read-only source review and pure mocked failure reproduction
FORMAL_ACCEPTANCE=false
DOCKER_LAUNCHED=false
ENGINE_LAUNCHED=false

FOLLOW_UP_STATUS=targeted fixes verified by seven pure mocked regressions
FOLLOW_UP_EXECUTOR_SHA256=20e6a13b0e78a519d50ee253cf9f9aa9b04ee5429a00a689350f64f54ed05645
FOLLOW_UP_TEST_SHA256=c5fa9e00777cbb424ec9127a519eaddb6c535c1e628239ac376e7cc592560d5d

The findings below describe the original reviewed revision. The coordinator's
subsequent fixes were independently checked against the follow-up hashes above;
the bounded checks passed. This is fix verification, not acceptance of a full
Linux execution or profile workflow.

Reviewed `studio/godot-addon/linux_executor.py` SHA256
`1a8a12bc63f5442c1db62be9390d3af80304dad00cb0e9b4081c1e47d7a3a6bb`.
Line references below apply to that source only. The coordinator owns subsequent
source/test edits and an active frozen profile probe; no source was changed by
this review. Pure reproduction replaced Popen, Job creation and file writes
with in-memory fakes, so it launched no helper or container and wrote no probe
files. This report is the only write.

## Findings

1. **Recoverable constructor failure becomes a permanent pending-CLI hold.**
   At lines 433–436, Job creation occurs before either pipe reader is started.
   A failed constructor whose Job was successfully cleaned up leaves no
   `cleanup_owner`, as intended. Finally kills/waits the exact gated helper,
   but lines 482–491 require exactly two readers to set `readers_stopped` and
   otherwise retain the process as an unfinished-reader hold. With zero
   readers ever started, this creates an unrecoverable module guard even after
   the helper exited. All three streams remain open on this branch.

   The pure reproduction observed `host_error=RuntimeError`, actual fake helper
   exit 2, `readers_stopped=false`, one `_INCOMPLETE_CLI_HOLDS` entry and
   stdin/stdout/stderr all unclosed. This is a recovery/handle-retention defect,
   not a clean-result bypass. Distinguish never-started readers from unfinished
   readers; close unused streams after proven process exit while retaining
   dirty evidence. Also close stdin explicitly when an error occurs before its
   normal close. Preserve genuine active-reader/process uncertainty.

2. **An exception in final helper shutdown skips Job/pipe/evidence cleanup.**
   `process.kill()` and `process.wait(timeout=3)` at lines 470–472 are outside a
   cleanup guard. An exception escapes the whole finally block before Job
   close/snapshot, reader retention or bounded evidence writes. The pure
   injected kill failure observed escaping `OSError`, zero Job close calls and
   zero `_INCOMPLETE_CLI_HOLDS` entries. The Job module can still retain a live
   owner in its registry, but this path need not add it to HOLDS or taint it;
   the caller receives no normal CLI record describing ownership.

   Each cleanup stage should run despite earlier cleanup errors. Preserve the
   process, pipe and Job owners whenever completion is unknown; report their
   status rather than abandoning finalization. A native terminate request is
   not proof that process wait or all descendants finished. An explicit
   `require_no_holds()` before Popen would also avoid creating another gated
   helper when a retained Job already prevents new CLI ownership.

3. **The planned clean-predicate strengthening must cover nonzero missing-object evidence too.**
   `_cli_clean()` at lines 504–508 currently does not require `job_owner`.
   `_missing()` at lines 306–311 and the removal predicate around lines 740–746
   duplicate the legacy host fields for expected exit 1. Actual `_cli()` now
   sets `host_error` for an uncertain owner, which protects the observed close
   failure path; no actual clean-result bypass was demonstrated here.
   Nevertheless, tightening only the exit-zero predicate leaves the expected
   missing-object proof shape inconsistent. Reuse an exit-independent host
   completion predicate requiring owner closed, zero observed, no retained
   handle and no taint, then check the expected exit separately. A missing or
   tampered owner snapshot should reject both ordinary success and removal /
   reconciliation evidence.

## Confirmed integration behavior

- Constructor errors transfer `cleanup_owner` into the local Job owner at
  lines 459–462; this avoids losing native handles retained by `cli_job.create`.
- A successful retry does not turn the original failed operation into a clean
  result: owner taint at lines 479–481 marks it dirty.
- The top-level run guard calls `require_no_holds()` before launching its
  normal work. The Job module also guards every create. Failure therefore does
  not authorize a new ungated Docker process, although finding 1 can accumulate
  unnecessary gated-helper holds inside cleanup attempts.
- Query uncertainty, native termination failure and native close failure are
  explicitly represented by the new owner module. It leaves the accepted
  GT02 bootstrap source unchanged.

No Docker, engine, native helper, plan update, commit or source change was made
for this review. Findings were sent directly to the coordinator for its next
source revision; this document does not certify later revisions.

## Targeted follow-up verification

Added only `studio/tests/godot/test_linux_cli_cleanup.py` and updated this report.
The actual command
`python -B 8-9-hh3d-3/studio/tests/godot/test_linux_cli_cleanup.py`
exited 0 with seven tests, against executor
`20e6a13b0e78a519d50ee253cf9f9aa9b04ee5429a00a689350f64f54ed05645`.
Popen and every Job factory are mocked; no native helper, Docker or engine was
launched. Tests write only bounded temporary evidence and remove it afterward.

The regressions verify:

- Constructor failure after successful constructor cleanup reaps the fake
  helper, closes all three pipes and creates no permanent pending-reader hold;
  the result remains dirty.
- A constructor's retained `cleanup_owner` is retried, its failed native close
  remains visible, and a dirty Job cannot become a clean result.
- Injected kill/wait failures do not skip Job close or evidence writing; the
  helper can be reaped after confirmed Job zero. If it still cannot be reaped,
  its process and pipes remain explicitly retained and the result stays dirty.
- A preexisting Job hold prevents even the gated Popen call.
- Nine missing or dirty Job-fact variants reject ordinary success and the
  shared expected-exit-1 completion predicate used for missing/removal proof.

An additional targeted case reproduced a reader `Thread.start()` failure:
joining that never-started reader could still escape cleanup. The coordinator
added guarded reader joins that skip `ident is None`. The seventh regression
now verifies that this failure closes unused pipes, writes dirty evidence and
does not invent an unfinished-reader hold. No further source review scope was
opened after this targeted verification. Executor source ownership remains
with the coordinator.
