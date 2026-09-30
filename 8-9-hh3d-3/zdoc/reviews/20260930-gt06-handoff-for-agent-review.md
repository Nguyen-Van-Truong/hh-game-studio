# GT06 handoff for independent review — 2026-09-30

## Purpose

This is a current handoff and review brief. It is diagnostic and does not change
the authoritative plan, sign acceptance, or provide a critic signature. Read the
O6 block in `zdoc/8-9-godot-blender-agent-studio-plan.txt` before changing
source or dispatching a formal campaign.

## Authoritative state

- `CURRENT_VALID_WP=GT-06`; GT-01 through GT-05 are accepted.
- GT-06 has **zero accepted formal pairs**. GT-07 through GT-10 remain closed.
- Implementation checkpoints: `9da2635b` (journal residency/transport) and
  `3f26d765` (recovery schema/watchdog retry). Use `git status` and `git log`
  for current HEAD; a hash embedded in its own handoff is not a live pointer.
- Verification after the redaction/Docker repair includes protocol `443` tests
  (exit 0, four skipped) and replay `683` tests (exit 0). The cancel admission/ACK transport fault tests, strict UNKNOWN sentinel checks, and the
  one-to-one transport-event binding test also pass. These are source checks,
  not formal acceptance and not a frozen source closure.
- The installed execution binding was reminted by atomic file replacement for the source
  delta, retaining the GT05 anchor: 215 source files, 217 verified execution
  files, verified closure `09733a55e3121db88b33dbaadca273cb66d2ddb9e6decfb38db765bb1ac46176`.
- Short HTTP allocation tracing found retained compiled regexes from cumulative
  credential redactors. The repaired instance-owned literal matcher preserves
  credential history and matching behavior. Isolated live allocations fell
  from 1,655,417 to 38,546 bytes after 35 credential generations; detailed
  evidence and scope limits are in the diagnostic lane. Full host soak remains
  required. Preflight at 19:53 was blocked by 92.165% system commit.
- O2 remains a separate authority-zero candidate tree and must not be merged
  before GT-06 acceptance.

## Historical failures retained

- Formal04 and formal05 ended `CPU INFRA_ABORT`.
- Formal06 ended as a product failure at terminal timeout.
- Formal08 failed the host private-commit trend/editor-handle criteria (pair 1
  was also `CPU INFRA_ABORT`).
- Host-only soak03 and soak04 remain diagnostics. Soak03 exceeded the retired
  O5 comparison; O6.3 supersedes that formula with the exact O1.4 windows.
- O6.3 `gt06-o6-host-soak-20260930-01` stopped after 28 batches with
  `HARNESS_FAIL` when watchdog sample 198 could not read Docker inventory.
  Its generic code does not prove timeout. Wrapper exit was 2 with clean Job;
  child exit/capture is missing. Supervisor return 1 is not that child exit.
- Independently, this prefix already exceeds the memory growth limit:
  baseline median 2-4 `30,650,368` bytes; max 5-27 `35,188,736` (114.806896%).
  Partial late/early max is 103.096124%; the full late window is absent.
  Fixing Docker inventory alone cannot establish readiness for formal.
- Soak04 stopped at batch 27 with a rejected command returning
  `CONNECTION_LOST_LOOKUP`/`UNKNOWN` during `client.connect` before request bytes
  were sent. It must remain a product/transport failure, not an infrastructure
  abort.

## O6 RAM diagnostic — corrected package

Raw package:

`studio/.local/reviews/o6-ram-20260930-02/`

Supervisor evidence:

`studio/.local/reviews/o6-ram-20260930-02-supervisor/`

- Run ID: `o6-ram-20260930-02`.
- 35,000 logical commands completed; the supervisor captured actual child exit
  code 0 (`process-exit.json`), with no stderr.
- Source closure: `b15f22fbecd4c1537ddf2d4c3e2509bdf9c10863ab667181965f3f1ade9e76ee`.
- O1.4 observation from the raw result: baseline median
  `17,952,768` bytes; main max `18,440,192` bytes, `102.715035%` of baseline;
  late max `18,423,808` bytes, `99.911151%` of the early-window max.
- Private-commit slope is `9.5514` bytes per logical command; tracemalloc slope
  is `8.5322` bytes per command.
- This is a one-process RAM diagnostic of the journal path. It is not a mixed
  host/editor pair, is not a formal O1.4 decision, and does not unlock GT-06.

## Existing offline editor control

`studio/.local/reviews/o6-control02-offline-result-02.json` records control02
with 2,809 samples. Its editor-handle diagnostic is `PASS` under authority 0
(the measured windows satisfy the median rule), and it explicitly preserves the
historical formal verdict. Reuse this existing control for comparison; no new
stock-control run is requested by this handoff.

## Required next sequence

1. Preserve the completed short attribution and redaction/Docker repair. Do
   not repeat these probes or regression suites unless source changes or new
   evidence warrants it. O2 can proceed in its worktree during the resource wait.
2. At dispatch, verify/freeze the complete source closure. The computed current
   residency closure has 54 files and hash
   `b43fb6f19cd1f363c925fa82c1c8d9469d75e7191d9e5ac6305d21c04c40851e`;
   this is not a completed-run binding. Docker uncertainty still fails closed.
3. Pass fresh O4.1 preflight and run a new 35-batch host-only soak under O6.3.
   If max/baseline exceeds 107% but passes O1.4, an additional fresh soak is
   required. Only sufficient soak evidence permits a new formal 2x35 campaign.
   Source/profile bindings and actual exits must be checked for each run.
4. Current implemented profile is O5/v6, hash
   `8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35`.
   Reuse existing stock control offline; do not rewrite historical v5 raw.
5. If formal evidence passes, prepare the `CRITIC_PACKAGE` for the owner’s
   independent read-only critics. Do not self-sign or tick GT-06.

## Guardrails

Do not resume formal01–08 or reuse IDs after a source change. Do not alter O1–O4
thresholds or timeouts, convert product failure to `INFRA_ABORT`, claim PASS from
a banner/caller field, or open GT-07 before GT-06 is genuinely accepted.
