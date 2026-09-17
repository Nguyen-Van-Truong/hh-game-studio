# GT06 S69 implementation checkpoint — not acceptance

GT01–GT05 remain accepted. GT06 remains in progress. The three Astra workers
reviewed implementation and evidence dependencies; these are not the two
independent acceptance verdicts required on a final frozen closure.

## Verified milestones

- `../20260918-gt06-s69-units-01/`: 434/434 replay/reviewer tests, no skips,
  146.685s, actual child/helper exits0, owned tree verified and listed source
  unchanged. This run precedes the final Stop completion-boundary fix; do not
  assign its full source inventory to the later campaign revision.
- `../20260918-gt06-s69-stop-units-01/`: 66/66 affected owner, Stop, campaign
  and assembly tests passed after the completion-boundary fix, no skips,
  21.646s, actual child/helper exits0, verified tree and unchanged source.
  Includes four deterministic completion/assembly/resume/previous-run Stop
  regressions. These tests supplement the prior full suite; their counts are
  not added to 434 as though all tests were distinct.
- Native `gt06-s69-saturated-stop-01`, `revoked-result-01`, and
  `stale-capture-01` passed 15/18/17 checks. Their bounded outer captures
  record actual child/helper exits0 and clean owned trees.
- `gt06-s69-managed-replay-01` reused the verified S65 repair02 receipt
  (`514a1f3a01ebab7f6f327a49170e4e9260a55310ee5c84b20c28f6bcf6a0ea14`).
  It passed on the current runtime, including 1.50000023841858m movement,
  pause/interaction/quit and seven fresh captures. The successful repair
  mutation was not repeated. The original causal fault/repair evidence remains.
- `gt06-s69-owner-smoke-01`: actual native handles verified for natural exit,
  exact fixed-slot Stop and injected constructor configuration failure. All
  owners closed with zero children and no retained wrapper handle. Capture v2
  verification passed for the natural exit; the failed setup never launched
  its target. This run precedes the added completion-boundary Stop checks.
- S68 campaign03 completed one combined batch: 1000 HTTP commands, 100 native
  create/undo/save/reload cycles, ready/start/ACK and joint readback accepted by
  the raw assembler. The coordinator then stopped it to repair owner defects:
  checked editor handle exit79, host exit1, parent Job closed/zero. This warm-up
  diagnostic is not a complete run or a performance PASS.

`native-progress.json` records 1124 raw artifact hashes across ten local roots,
with selected small files copied under `captures/`. Raw roots stay under
`studio/.local/reviews/`. This progress index is not a portable replacement for
the complete native evidence. Every lane retains its own source binding.

## Implemented corrections

The benchmark owner returns `cleanup_owner` even when constructor cleanup
succeeds. It closes the actual retained Popen process handle after observing
exit; checked failure retains ownership for retry, while uncertain close
results suppress double-close. Evidence now uses
`HH-GT06-BENCHMARK-CAPTURE-2` and requires explicit wrapper-handle proof.
Historical v1 captures are preserved and cannot satisfy the v2 verifier.
Child cleanup derives retained handle counts from the actual owners/probes.

`BoundRun` carries immutable serialized run bytes and the verified source,
toolchain and profile digests. Dataset assembly rejects unbound or mixed runs.
The final profile1.1 dataset schema and limits are unchanged. A hash envelope
does not replace native ownership or artifact verification.

The operator Stop file is `run-NN-attempt-NN/stop-request.json`, bounded to
4096 bytes and bound to the exact run/source/campaign. Duplicate keys, stale
bindings and extra fields fail closed. A stopped attempt cannot resume.
Completion polling rechecks Stop after observing terminal exit, and campaign
boundaries check all fixed attempt slots before resume, launch, publication
and final dataset output. An older attempt's Stop is also checked while a
later run is active. A request after the final completion check is outside
that invocation; any later resume still rejects its persisted Stop latch.

Publish the following payload atomically using an exclusive temporary file
and no-overwrite rename, copying bindings from that attempt's `context.json`:

```json
{
  "schema": "HH-GT06-CAMPAIGN-STOP-1",
  "run_id": "<context.run_id>",
  "source_closure_sha256": "<context.source_closure_sha256>",
  "campaign_sha256": "<context.campaign_sha256>",
  "reason": "OPERATOR_STOP"
}
```

## Reuse and remaining work

The S69 dependency map is
`../20260918-gt06-s69-owner-review/requirements-map.md`. Existing S68 GUI
complete02/stop02 dependencies are unchanged. New service adversaries and the
managed replay cover the affected runtime. Draft worker files are supporting
material only; executed results are recorded separately from those drafts.
The later `integration-followup.md` records the worker checks and supersedes
that historical map's requests for remints and unresolved owner fixes.

The full benchmark still requires ten fresh host/editor pairs, each with five
warm-up and thirty measured batches, 1000 commands and 100 native cycles per
batch. Partial attempts are never spliced into a dataset. Complete verified
runs may resume only on the same source/machine/profile. No thresholds,
sample counts, or 7410-second per-run owner cap were relaxed. Do not run other
engines or heavy test lanes during this measured campaign.

After a successful campaign, freeze the final requirement/evidence mapping
and obtain two independent critic verdicts before accepting GT06. GT07
recovery/concurrency, GT08 CI and physical Android, GT09 conformance and GT10
package/upgrade/rollback/handoff remain. HH World is a separate plan after
GT10. There is no reliable total completion date yet.

## Windows ownership references and lessons

Windows children normally inherit Job membership; nested parent limits can
still apply. A hidden window does not establish detached ownership. These
facts help explain why a background launch alone is insufficient, but do not
prove the cause of the old campaign01/02 interruptions.
[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs).

`TerminateProcess` returns before termination necessarily finishes, so the
controlled campaign03 stop waited on the checked process handle and captured
its exit. A later process-list absence is not equivalent evidence.
[TerminateProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess).

Keep command cwd consistent with patch paths. Preserve raw bytes and narrow
Git whitespace attributes for evidence instead of rewriting CRLF artifacts.
Record a source map for every test lane and rerun only affected verification.
