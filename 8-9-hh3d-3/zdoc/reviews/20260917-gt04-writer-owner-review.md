# GT-04 writer owner integration — bounded source review

2026-09-17, Asia/Saigon. Initial read-only review of the new writer owner,
writer-session, client-ledger and adjacent queue/transport boundaries, followed
by a coordinator-assigned ledger fix and inert tests for finding 4. This is not
an acceptance critic verdict. No native, registry, filesystem journal or engine
test was launched by this worker.
Production source was changing under its assigned coordinator; the hashes below
identify the final source read by this review, not a frozen acceptance closure.

## Findings reported to the coordinator

1. **Corrected during review: delivery after revoke/credential expiry.** The
   initial submit implementation persisted and returned a successful observation
   without rechecking the current grant after native execution. Draining an
   already-authorized effect does not itself authorize later receipt delivery.
   The added `_deliver` gate checks grant identity under the session mutex and
   applies fresh-read Stop/deadline checks separately from historical delivery.
   It retains the actual terminal receipt when delivery is denied.

2. **Corrected during review: native/JCS revision hash domains.** The initial
   `_observed` recalculated the native revision from an IPC-decoded snapshot.
   Native JSON preserves `1.0` and `-0.0`; IPC JCS normalizes these numbers. Native
   snapshots contain Blender floats, including `units.scale_length`, so this
   could reject valid readback after a real effect. The updated implementation
   preserves the authenticated native revision and hashes the named JCS
   observation separately.

3. **Corrected during review: unexpected failure during writer acquisition.**
   The earlier `lease()` held the owner only for `outcome_unknown` or a held durable owner.
   `DurableBlenderSession.acquire_writer()` invokes the journal before its
   native-arm exception handler. A raw `OSError` when the journal guard releases
   can therefore follow a persisted lease and leave both owners unheld;
   `Journal._mutating` classifies `JournalError` but does not wrap this raw error.
   The current owner now holds both its facade and durable session and raises
   typed `BLENDER_WRITER_ADMISSION_UNKNOWN` with `outcome_unknown=true` on
   unexpected acquisition failures. Known typed refusals such as `LEASE_BUSY`
   remain ordinary no-effect refusals. This resolves the source classification
   gap; no duplicate scene effect was claimed from that gap.

4. **Corrected after coordinator finding: project-wide command dedupe.** The
   original private alias included the session ID and `_retry` looked up only
   that alias. A second authenticated session could therefore reserve the same
   public command ID again. The owner-test worker reproduced a second modeled
   COMMITTED effect after acquiring a new native-model fence; pending history
   returned a capacity error instead of enforcing command ownership.
   The ledger now reserves `(project_id, command_id)` across sessions before
   alias lookup/admission. Foreign-session retry/admission returns
   `BLENDER_LEDGER_COMMAND_OWNER`, never the original receipt, and is a known
   refusal that does not hold the owner. Foreign-session lookup still returns
   `BLENDER_LEDGER_COMMAND_NOT_FOUND`. Native aliases remain session-scoped for
   the private protocol. Complete history validation rejects duplicate public
   IDs across sessions, including a forged but otherwise valid second intent.

## Boundary observations

- Historical replay validates the registered grant and complete original
  command/native binding; pending history returns UNKNOWN without a permit.
  Fresh execution remains serialized by `_work`; public dedupe identity spans
  every session within the project-bound ledger history.
- Native dispatch forwards the original absolute request deadline and exact
  registered lease fence. Stop/revoke before the PREPARED-to-DISPATCHING
  transition deny new authority; an already-authorized effect may drain.
- The corrected `_record_terminal` attempts persistence once. A lost append,
  barrier or guard-release response cannot trigger a second finish with a
  fabricated replacement UNKNOWN response.
- `_deliver` performs no journal/native/source/Job wait while holding the session
  mutex. This avoids reversing the ledger-to-session lock order used by output
  validation. Successful wire encoding continues to reject changed secret
  redaction instead of corrupting the observation hash.
- Owner discovery filters capabilities to inspect and the five connected edit
  operations. Save/checkpoint/export are absent there and rejected as not
  connected; no durable public ACK or native preview is claimed.

Observed SHA-256 values, paths relative to `8-9-hh3d-3/`:

| File | SHA-256 |
| --- | --- |
| `studio/host/blender/client_writer_owner.py` | `963bc45584ab549e4ed16fb52a9d46821446f9bd58a39b4346a1d0d31c541e72` |
| `studio/host/blender/client_writer_session.py` | `93d7c461c3550661caef1d4b8dd994401e103cdfa3c5623abd45148df7ca4a3c` |
| `studio/host/blender/client_ledger.py` | `67cd3704ab9e5a3f36707f5002b1e728c879d13503a671354cde4b0927bc40de` |
| `studio/tests/blender/test_client_ledger.py` | `bdb7be1ddbab91fae650ab59902f61f0d9577690b58974a6282e1bc1d6bf726a` |

The focused inert ledger command completed with actual Python process exit 0:

```text
python -B -m unittest discover -s 8-9-hh3d-3/studio/tests/blender -p test_client_ledger.py -v
Ran 46 tests in 6.087s
OK
```

This covers pending/terminal ownership, changed payload/revision, concurrent
cross-session admission, forged duplicate history, receipt confidentiality,
known-refusal hold classification and a valid fresh command from the next
session. The owner-test worker separately reported 37/37 passing with captured
exit 0 after the fix, including the previously failing cross-session cases;
that report is coordination information, not a native acceptance claim.

All four reported source findings are resolved at these observed hashes.
Later native proof on a stable closure remains required. The requested preview
and protected-publication design review was paused to fix finding 4; it is not
represented here as completed integration work.
