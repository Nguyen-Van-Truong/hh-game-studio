# S106 bounded prefix comparison

AUTHORITY=0. **NON_REPRODUCED. The identical-prefix branch is closed; no identical
retry is justified.** This packet is not a final critic verdict, GT06 acceptance,
F13/F14 dataset, full-run PASS, no-leak proof or runtime-repair authorization.

`gt06-s106-handles-prefix-01` completed six captured batches and stopped at the
planned `S106_PREFIX_BOUNDARY`. Each batch has 1,000 HTTP commands and 100 native
cycles: 6,000 commands/600 cycles total. Both original gates were recorded as
PASSED before PSS capture. Neither gate, timing, RSS nor counter baseline was
relaxed. The unchanged comparison uses exactly batch 4 as the batch 5 baseline.

| Observation | Batch 4 | Batch 5 | Change |
| --- | ---: | ---: | ---: |
| Sample editor handles |563|555|-8|
| PSS captured entries, target before/after |563|555|-8|
| PSS Event type count |118|114|-4|
| PSS Thread type count |47|44|-3|
| PSS IoCompletion type count |12|11|-1|
| Unavailable type bucket |192|192|0|
| Host handles, including observer before/after |204|204|0|
| Editor ObjectDB/resources |71128 /6|71128 /6|0|
| PSS total duration (ms) |8.4505|10.0524| — |

All other type buckets are unchanged. The complete type-count table is in
`summary.json`. These are counts across two snapshots of the same retained
process identity, not an identification of particular handles or kernel objects.
The packet does not infer which objects persisted, were released or were reused.
There is no excess to attribute in this run. PSS can perturb the next READY and
status-gap interval; no observer time/memory is subtracted. There is no post-idle
series or general leak/root-cause proof.

Editor handle series: 563,557,557,555,563,555. Host handles: 203,203,204,204,204,204.
Editor ObjectDB 71128/resources 6 stay constant. Maximum HTTP gap 905.7962 ms is at
batch 2; maximum native gap 714.183 ms is at batch 5. Batch 5 combined gap 714.183 ms
is below the unchanged 2,000 ms gate. HTTP transport failures are 0. Both PSS
snapshots have errors 0 and all recorded snapshot/marker/observer resources
released. This does not resolve the separate S102 native latency failure.

## Actual exits and cleanup limits

Host target 46864 actual/helper exits 1/1. Import target 53260 actual/helper exits 0/0.
Editor target 23356 actual exit is **UNKNOWN**, helper exit 2. Forced diagnostic
teardown is not natural editor exit proof. Host/editor/import Jobs are recorded
zero/closed; retained probes, wrapper handles and threads have their scoped
release observations. Import wrapper native-handle close still has no explicit
receipt and remains UNKNOWN.

The passive outer observer records Python 22376 actual exit 0, with matching
start identity `2026-09-19T05:41:03.4757464Z`, at `2026-09-19T05:50:12.5091162Z`.
It retained the Process handle and added no Job. Managed Dispose is recorded;
a native CloseHandle return and the enclosing PowerShell process exit are not
observed. The original runner result's self-exit UNKNOWN is preserved byte for
byte; the separate `outer/` receipt supplies the scoped Python actual exit.

No Stop request exists or was exercised in this prefix. The retained helper
checks the original Stop reader before launch, each owner tick and after exit;
the original reader requires the exact run/source/campaign hash and rejects stale
or malformed requests. The six-batch prefix has its own context binding, shown
in `summary.json`; do not reuse preflight Stop bindings. This is static path
review plus absence observation, not runtime Stop acceptance evidence.

## Byte domains and scope

`raw-selected-domain.json` lists only explicitly selected original metadata,
logs, native/command/batch artifacts, gates/PSS, outer receipts, six frozen
diagnostic files, exact passive observer and two supporting source files.
Each has one exact portable copy. `manifest.json` separately hashes the portable
path domain and all derived packet files; original and portable domain hashes
must not be interchanged. All 36 batch-capture references, gate/sample/context
bindings, helper closure, profile literals and outer identity are checked.

`source-audit.json` records a bounded hash audit of all 53 runtime source paths,
six frozen diagnostics, four original helper pins, observer, Python and Godot
executables. The 53-file closure remains
`7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`;
profile remains `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
Executable images and the full runtime are not duplicated. Packet-only
verification checks the audit's retained bindings, not absent live bytes.

Excluded: journals, commandstore, guards, cache/private-environment trees,
general generated project contents, secrets and any unselected raw paths.
No excluded-tree inventory or recursive raw hash sweep was performed. The
builder screens selected text for high-confidence secret patterns/JSON keys;
this is a bounded screen, not a claim about arbitrary encoded secrets.

## Reproduction

From the HH3D directory (`8-9-hh3d-3`), one-time retention:

```powershell
python -B zdoc/reviews/20260919-gt06-s106-prefix-result/build_packet.py
```

Repeatable packet-only verification:

```powershell
python -B zdoc/reviews/20260919-gt06-s106-prefix-result/verify_packet.py
```

The builder refuses to overwrite its manifest. `parse_prefix.py` independently
derives `summary.json`; the verifier checks byte hashes and reproduces that
summary without executing the retained runtime/diagnostic helpers or launching
an engine. `verification.json` retains the verifier output. VERIFIED_PACKET_ONLY
is an evidence-integrity result, not benchmark acceptance. No commit was made
by the packet author.
