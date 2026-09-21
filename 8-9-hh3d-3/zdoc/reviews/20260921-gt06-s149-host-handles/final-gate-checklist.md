# S149 terminal → GT-06 formal-retry checklist

Read-only checklist derived from the current tools plan (Revision S149), the
S149 decision/progress reviews, and the GT-06 evidence rules. S149 remains an
`AUTHORITY=0` host-only diagnostic. It cannot be counted as F13/F14 evidence, a
formal run, a warmup pair, or a GT-06 PASS.

## Seal S149 before interpreting it

- [ ] Obtain the supervisor/launcher terminal receipt and preserve the raw
  run directory under the fresh S149 run ID. A scheduler snapshot (`instances=0`
  or `last_result`) is state only; it does not prove liveness or completion.
- [ ] Freeze a complete, canonical manifest of every raw and derived file,
  with relative paths and per-file SHA-256. Verify missing, extra, stale, and
  mismatched files before reading conclusions. Do not overwrite the run ID or
  repair the packet by rerunning the engine.
- [ ] Retain the entire 11-batch prefix/all-attempts history, including the
  first failing row, Stop/abort records, command rows, checkpoints, PSS census
  files, stdout/stderr, and cleanup receipts. A banner, partial prefix, or
  caller-supplied `PASS`/exit field is insufficient.
- [ ] Bind every census to the owned helper PID, process-start identity, and
  executable. Require PSS `OBSERVED` with matching PID/start identity, complete
  redacted entries/type counts, and released marker/snapshot/process resources.
  Any `UNKNOWN`, identity mismatch, incomplete census, or cleanup uncertainty
  stops interpretation; preserve it as a gap.
- [ ] Read actual target, helper, and wrapper exit records independently. Keep
  target/editor exit distinct from helper/wrapper exit; never infer a natural
  exit from a banner or from a scheduler result.
- [ ] Verify cleanup independently: Job configured/assigned/closed, active
  count zero, untainted, no failed operations, retained owner/probe/wrapper
  handles released, owned process tree zero, producer/journal closed, no live
  threads, and source bytes unchanged. Missing exit or cleanup proof is not a
  pass even when the command rows look complete.
- [ ] Verify Stop was not silently removed or bypassed. Keep timeout, priority,
  baseline, profile, workstation, and original command/gate behavior unchanged.

## Decide what S149 established

- [ ] Compare the child’s original gate samples with the external PSS samples
  only with their timestamps and phase recorded. A post-sample ACK wait, timer,
  or other observer timing difference is an attribution gap, not a causal leak
  finding. Numeric handle reuse or redacted attribute matches do not prove
  kernel-object identity.
- [ ] If growth does **not** recur, record non-reproduction and retain S147’s
  failure. Do not loop host-only retries and do not claim “no leak” or root
  cause.
- [ ] If a descriptor class is bound by clean PSS evidence, write one narrow
  repair hypothesis with its affected source paths and expected postcondition.
  Do not change a gate, baseline, timeout, profile, RSS policy, or workload to
  make the observation pass.
- [ ] If source changes are justified, mint a new source freeze/run ID and run
  focused regressions for the affected capability. Do not attach S149 or S147
  signatures to the changed source and do not reuse old formal IDs.

## Preconditions for any fresh formal GT-06 retry

- [ ] Coordinator records the sealed S149 disposition and any focused-repair
  result before dispatch. The formal retry remains closed while S149 evidence,
  source closure, or a repair hypothesis is unresolved.
- [ ] Freeze the exact formal source/runtime/profile/binary closure before the
  run. Include all code, schemas, fixtures, imports/linked dependencies,
  configuration, and manifests; use canonical sorted relative paths and
  per-file SHA-256. A dirty Git HEAD does not replace this manifest.
- [ ] Use a fresh formal run ID/command IDs and ten fresh host/editor pairs,
  each with the unchanged 35-batch campaign: batches 0–4 warmup and 5–34
  measured, 1000 HTTP commands plus 100 native cycles per batch, same process
  identity through the pair, and the original ready/start/joint/ACK/Stop
  records. Do not combine partial attempts into a PASS or use S149 smoke as a
  warmup pair.
- [ ] Verify every measured batch against the locked original gates: host and
  editor RSS each ≤110% of that pair’s batch-4 baseline; host OS handles and
  editor objects/resources/OS handles each ≤ their batch-4 baseline; a single
  over-baseline sample fails, even if it later falls. Missing required counters
  are gaps, not zero; no rebaseline or overhead subtraction.
- [ ] Produce the complete dataset and raw/hash/schema/limits closure, including
  all attempts, command IDs, phase timings, GC/import observations, counters,
  postconditions, actual process roles/PIDs/start/exit records, and cleanup
  artifacts. The packer must parse real host exits and reject caller-provided
  exit integers, stale files, missing files, hash drift, schema drift, and
  incomplete/aborted runs.
- [ ] For every pair, independently verify actual target/editor/helper exits 0,
  owned tree zero, Job closed/zero/untainted, and all retained owner handles
  released. Keep retained owner handles separate from the live OS handle count
  used by the campaign gate.
- [ ] Close the final source/review/raw manifest and a requirement→test→evidence
  map. Orphan requirements, unexplained warnings/errors, unknown exits, or
  unproven postconditions keep GT-06 open.
- [ ] Obtain two independent read-only critics on the same frozen final source
  and evidence hash. Each must explicitly record `PASS` and `TICK=yes`; neither
  may rely on the other’s verdict. Coordinator verification is not an
  independent critic signature.
- [ ] Only after all boxes above are complete may the coordinator ACCEPT GT-06
  and open GT-07. Until then preserve S147/S149 failures and diagnostics as
  `AUTHORITY=0` historical evidence.

The checklist does not authorize a retry or alter the GT-06 DoD; it identifies
the evidence that must exist before an owner-approved formal retry can be
considered.
