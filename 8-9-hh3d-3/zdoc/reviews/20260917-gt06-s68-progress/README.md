# GT06 S68 implementation checkpoint — not acceptance

GT01–GT05 remain accepted. GT06 remains in progress. No review by this
implementer, stopped worker, or historical critic is an acceptance verdict.

## Verified milestones

- `../20260917-gt06-s68-units-03/`: 415/415 replay/reviewer tests,
  no skips, actual child/helper exits0, owned tree verified, listed source
  unchanged. `invocation.json` binds 140 listed files; this is a unit source
  inventory, not the complete final native acceptance closure.
- `../20260917-gt06-s68-journal-contract-03/`: 62/62 tests against the
  packed-index VerifiedJournal, actual exits0 and unchanged listed source.
  Previous failed and successful source versions remain in directories01/02.
- Actual Tk `gt06-s68-reviewer-complete-02` and `stop-02`: keyboard Play,
  HTTP inspection/capture, priority Esc/Stop and owned cleanup passed.
  Driver captures bind actual child/helper exits0 and clean owned trees.
- `gt06-s68-native-cycle-01`: one actual GUI create/undo/save/reload cycle
  on native schema1.2.0 passed. This diagnostic does not exercise the full
  host-command/start-permit/ACK campaign or prove performance thresholds.
- `gt06-s68-owner-smoke-02`: real child natural exit verified; stopped owner
  cannot later report successful completion. Both owned trees closed/zero.

`native-progress.json` hashes retained local raw artifacts and records copies
of selected captures in `captures/`. Raw roots remain under `studio/.local/`;
this progress package is not a portable replacement for all native evidence.
Each run keeps its own source binding. Earlier results are not reassigned to
later source versions. Unit source hashes were checked against disk again
when this inventory was collected.

## Changes and limitations

VerifiedJournal still takes the accepted writer lock, verifies the complete
regular single-link journal bytes and fsyncs before returning cached history.
Only exact matching bytes/identity/policy reuse the decoded indexes. Compact
offsets and per-project command indexes retain every receipt and tombstone.
Accepted core Journal is unchanged. History hashing remains O(file bytes).

Command raw schema1.1.0 retains every lookup attempt and terminal response.
Only uncertain connection loss is reconciled using the same command ID within
the original deadline; mutation is never resubmitted. Native schema1.2.0 uses
ready -> 1000 host commands -> bound start -> 100 native cycles -> joint sample
-> ACK with fresh native counters. Host and native clocks remain separate.
The campaign keeps 10 fresh process pairs and 35 batches per pair, including
5 warm-up batches. Profile mix, thresholds and 7410-second owner cap remain.
Offline assembly verifies raw hashes, source, identities, clocks and counters.
Complete captured runs can resume; partial/failed samples never join a dataset.

The old single1000-command diagnostic completed in32.282s. It is not a complete
benchmark or a controlled speedup comparison. The old command-only residency
failed in batch12 after11 complete batches, at a terminal identity guard.
The matching receipt is COMMITTED in the journal, but the old driver did not
record the returned lookup response, so the cause remains unproven. Actual
child/helper exit1 and closed/zero ownership were captured. Batch10 RSS was
37,933,056B (+9.197% over batch4); no35-batch memory claim is made.

Campaign01 and02 were externally interrupted during their first native batch,
around cycles67/68. Their logs stop without child/parent failure or exit/Job
cleanup records. Later process inventory found no campaign Python/Godot
processes; that observation is not an actual exit or Job-close attestation.
Neither run is resumable as a successful measurement. Start-Process Hidden
also did not preserve02 through the session interruption. Preserve both raw
prefixes; use a fresh process pair, never splice their samples.

## Remaining work

Run the exact combined campaign without interruption, check its measurements,
repair any actual failures, and finish the GT06 requirement/evidence matrix on
one frozen closure. Two fresh independent critics are still required before
coordinator acceptance. Then GT07 recovery/concurrency, GT08 CI and physical
Android, GT09 conformance, and GT10 package/rollback/handoff remain. HH World
is a separate plan after GT10. No reliable total completion date is known.

From `8-9-hh3d-3`, use a fresh campaign ID:

```text
python -B studio/tests/replay/run_benchmark_campaign.py --campaign-id gt06-s68-campaign-03
```

Do not run native engines, full suites or heavy diagnostics concurrently with
the benchmark. Keep old successful lanes and their source hashes; repeat only
affected verification after a change. Current plan is the sole progress source.
