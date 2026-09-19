# S105 retained diagnostic results

AUTHORITY=0. This is a derived retention/audit packet, not a final critic verdict,
GT06 acceptance, formal campaign, F13/F14 dataset, leak finding, or runtime repair.
The original five raw roots and generated child scripts were copied byte for byte
where selected. Original misleading diagnostic summaries remain unchanged.

## Actual outcome

| Run suffix | Batches | Classification | Maximum HTTP / native gap (ms) |
| --- | ---: | --- | --- |
| preflight-01 | 0 | Collector prepare failure: missing `os`; engine did not start | unavailable |
| preflight-02 | 1 | Planned diagnostic boundary | 496.3064 / 623.821 |
| 01 | 5 | Collector `KeyError: run_id` at baseline | 529.8975 / 650.25 |
| 02 | 5 | Collector `NameError: _write` after capture, before persistence | 1965.7287 / 746.408 |
| 03 | 6 | Planned diagnostic boundary; PSS baseline only | 481.3738 / 779.422 |

Each captured batch contains 1,000 HTTP commands and 100 native cycles. Total:
17 batches, 17,000 commands and 1,700 native cycles; none are acceptance samples.
All four engine runs report zero HTTP transport failures. There are 102 verified
batch-capture references: command, native, joint, ack, ready and start per batch.
This is an exact-reference check, not independent execution of the benchmark.

Run03 editor handles were `565,559,555,555,559,555`, host handles stayed203,
and editor ObjectDB/resources stayed71130/6. Batch5 passes the unchanged counter
comparison with exact batch4 baseline559 and the unchanged 2,000ms status gate.
No failure-boundary PSS snapshot exists because the handle-growth gate did not
recur. The sole snapshot is `raw/gt06-s105-handles-03/pss/batch-04-after-gate.json`:
559 entries, retained process identity matched, target559 before/after,
observer203 before/after, total12.8305ms, errors0 and PSS cleanup all released.
Its canonical sample hash matches the retained batch4 sample.192 types are
unavailable. Numeric handle values are not object identity; observer effects,
causality and leak attribution remain unknown. No runtime repair is justified.

## Lifecycle limits

All five host target actual exits are1, preserved in each `host-owner/process-exit.json`.
The four engine runs have import actual/helper exits0. Editor helper exit2 is
recorded, while actual editor target exit is missing (`TARGET_EXIT_NOT_RECORDED`).
Host/editor/import Jobs are observed zero and closed; recorded wrapper/probe
handles and relevant threads are released. Import wrapper process-handle close
has no explicit receipt. The outer runner actual exit is absent from these raw
roots. Cleanup counters and helper exits do not replace missing target exits.
Preflight01 has no child failure/terminal record because prepare failed before
the guarded engine body. Its original `engine_started=true` is unsupported.

## Hash domains and exclusions

`raw-selected-domain.json` binds original repository-relative source paths to
exact selected bytes and their portable paths. This is deliberately a selected
domain, not a complete raw-root inventory. `manifest.json` separately binds all
portable exact copies and derived packet files. One physical exact copy is kept
per selected source; different path domains have separate canonical digests.
Generated children are included and checked against all five context hashes.
Four terminal/context bindings and the one PSS/sample binding are also verified.
Source closure/profile declarations remain original; the packet does not claim
to revalidate the live53-file runtime or prove which unpinned adapter bytes were
loaded by a historical child.

Only top-level selected metadata, batch artifacts, host logs/lifecycle records,
benchmark input/output JSON, PSS and generated children are copied. No cache,
private environment tree, journal, command store, guard, secret, or general
project/source tree is retained. The builder never recursively enumerates or
hashes excluded raw trees. The machine-readable exclusion scopes are in the raw
domain file. A bounded secret-pattern/JSON-key screen covers the selected text;
it is not a general guarantee about arbitrary encoded secrets.

## Lessons from this collector

The historical helper called file presence plus empty terminal errors
`GATE_RECORDED`, so collector failures01/02 received that misleading label. It
also hardcoded engine start. Correct derived classification must read actual
failure, lifecycle and snapshot evidence instead of trusting that label.

The retained generated child03 lines69-76 invoke PSS inside the original gate
exception handler before the runtime writes `child-failure.json`. A collector
exception could replace the original failure; `original_gate_recorded` is an
asserted boolean without a preceding durable gate receipt. The future collector
should retain the original gate result before probing, bind the baseline and
sample, and stop on UNKNOWN or cleanup uncertainty. These are diagnostic
collector lessons, not evidence supporting changes to the frozen runtime/gates.
No corrected future helper behavior is claimed for the retained historical runs.

## Reproduction

From the HH3D directory (`8-9-hh3d-3`), the one-time retention command was:

```powershell
python -B zdoc/reviews/20260919-gt06-s105-result/build_packet.py
```

The builder refuses to overwrite an existing manifest. Reproduce verification
using only files within this packet:

```powershell
python -B zdoc/reviews/20260919-gt06-s105-result/verify_packet.py
```

`verification.json` is the captured packet-only verifier output. Its status
`VERIFIED_PACKET_ONLY` means byte/reference/derived-summary checks succeeded;
it is not a benchmark PASS. The verifier does not import engine/runtime code,
touch original raw roots, start/control processes, or grant acceptance.
