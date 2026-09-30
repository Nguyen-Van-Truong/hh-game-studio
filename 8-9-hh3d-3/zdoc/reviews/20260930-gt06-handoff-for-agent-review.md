# GT06 handoff for independent review — 2026-09-30

## Purpose

This is a current handoff and review brief. It is diagnostic and does not change
the authoritative plan, sign acceptance, or provide a critic signature. Read the
O6 block in `zdoc/8-9-godot-blender-agent-studio-plan.txt` before changing
source or dispatching a formal campaign.

## Authoritative state

- `CURRENT_VALID_WP=GT-06`; GT-01 through GT-05 are accepted.
- GT-06 has **zero accepted formal pairs**. GT-07 through GT-10 remain closed.
- Current HEAD is `3f26d765` (`GT06: harden journal residency and transport
  recovery`), the one coherent O6 repair commit.
- Verification now includes protocol `441` tests (exit 0, four skipped) and
  replay `678` tests (exit 0). The cancel admission/ACK transport fault tests, strict UNKNOWN sentinel checks, and the
  one-to-one transport-event binding test also pass. These are source checks,
  not formal acceptance and not a frozen source closure.
- The installed execution binding was reminted atomically for the committed source
  delta, retaining the GT05 anchor: 215 source files, 217 verified execution
  files, closure `38dbf542016cfecd7cfcb477bccb3cef57fd12f9a9e30566ed9277e1a79b70b5`.
- O2 remains a separate authority-zero candidate tree and must not be merged
  before GT-06 acceptance.

## Historical failures retained

- Formal04 and formal05 ended `CPU INFRA_ABORT`.
- Formal06 ended as a product failure at terminal timeout.
- Formal08 failed the host private-commit trend/editor-handle criteria (pair 1
  was also `CPU INFRA_ABORT`).
- Host-only soak03 and soak04 remain diagnostics. Soak03 exceeded the retired
  O5 comparison; O6.3 supersedes that formula with the exact O1.4 windows.
- O6.3 gt06-o6-host-soak-20260930-01 stopped at 28 batches with HARNESS_FAIL after watchdog sample 198 could not read Docker inventory. Raw watchdog error/stop and clean Job closeout are retained; the repair retries one transient Docker read and still aborts closed.
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

1. Finish review of the O6 transport repair and its focused protocol/reconcile tests.
   Record phase, exception, errno/winerror, attempt count, and whether bytes
   were sent. Retry only pre-send `connect` failures with the O6 bounded policy;
   after bytes are sent, reconcile by lookup and never blindly resend.
2. Keep the source WIP uncommitted until the repair is reviewed as one change
   set; retain raw diagnostic packages and do not rewrite historical verdicts.
3. Freeze one complete source closure, pass a fresh O4.1 preflight, then run a
   new formal 2x35 host/editor campaign with exact O1.4 metrics and actual exits.
   Use a new run/command ID after any source change.
4. If formal evidence passes, prepare the `CRITIC_PACKAGE` for the owner’s
   independent read-only critics. Do not self-sign or tick GT-06.

## Guardrails

Do not resume formal01–08 or reuse IDs after a source change. Do not alter O1–O4
thresholds or timeouts, convert product failure to `INFRA_ABORT`, claim PASS from
a banner/caller field, or open GT-07 before GT-06 is genuinely accepted.
