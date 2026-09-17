# S75: isolate diagnostic evidence from the editor asset index

GT06 remains in progress. S73 launch2 failed after 2133.782 seconds at batch9:
editor handles566→568 and Objects71175→71213. Source/profile were unchanged.
The real host exit is1; the editor native exit is absent, with wrapper2 kept
separate. Owned Jobs reached zero/closed and handles were released. Ten captured
batches do not provide a complete35-batch run. The failure seal and all partial
samples remain under `failure/` (manifest SHA256
`4c8ed5ab625e7c953a4e723c1b0e7c1daa74e352cdc5ecea0367391c514a3e36`).

The disposable explicit-scan probe found38 new JSON files caused38 new
FileSystem TreeItems and76 Objects, with stable Node identities, RichText
paragraphs and cached resources. A pre-import `benchmark/.gdignore` prevented
this increase. `editor-files-proof/` contains the frozen probes and limitations.
The final paired arms use the same `scan_sources()` path as the pinned editor's
focus-triggered scan. An earlier ignored arm timed out because its harness
awaited `filesystem_changed`, which is not emitted for no-change scans. Its
native86 and cleanup are retained; the corrected waiter uses `sources_changed`.
This identifies an instrumentation retention mechanism. It does not prove that
the original +38 Objects were exactly19 indexed files, explain its extra two
kernel handles, or resolve the earlier RSS/latency failures.

The production correction is confined to benchmark preparation, native guard
and assembly: generate a nonempty ignored marker before import, bind its exact
bytes in the native source set, and require it in the full-run assembler. Data
continues through FileAccess; game assets, raw evidence, counters, five warmups,
thirty measured batches, ten fresh pairs and all original thresholds remain.
The native source map also explicitly includes the non-Python perf schema.
Preflight found and corrected the assembler's old nine-file expectation and
the text reader's BOM normalization before starting any new full campaign.

Validation on the final runtime49 closure
`638304f54851366ac2a79a792a8009406fc927c3c6c410ad8f65cc2dd9b14995`:

- `affected-units-01/`:115/115, no skips/errors/failures, actual target20792
  exit0, wrapper51500 exit0, bounded180s runner, tree clean and source unchanged.
- `gt06-s75-native-02`: actual import49440/editor36144 exit0, source unchanged,
  owned Jobs zero/closed. One native semantic cycle only.
- `gt06-s75-ignore-bom-01`: BOM-prefixed marker rejected before any cycle,
  actual native19668/wrapper exit86, no scene change, Job zero/closed. Stock
  scan-thread warning on this deliberate early exit is retained, not permitted
  in a successful lane. Historical native01/guard01 precede the final byte guard.
- `native-validation/` seals exact copies and raw inventory; manifest SHA256
  `96630075d5fd6261fd4e021e6bb7f9b33332034e806018d4659393588d8aac89`.

The first native collector incorrectly expected the successful-capture-only
`actual_process_exit` field on negative captures. It was repaired to verify the
bound real `process-exit.json`, matching start PID and wrapper code, and resumed
only byte-identical partial copies. No native run was repeated for this metadata
repair. The guard01 collector's stricter stderr assertion is kept as failed;
the final BOM negative explicitly preserves its known early-exit warning.

`owned_telemetry.py` is supplemental read-only priority/commit/fault sampling
with PID+creation+executable identity checks. Its self-test does not establish
the campaign's priorities, RSS behavior, or kernel handle cause. `next/` prepares
dependency projection and sealing; its draft is not a final campaign verdict.
Two fresh independent critics still require the completed frozen closure.
Source changed, so S73 cannot resume as S75. Fresh campaign
`gt06-s75-campaign-01`, launch1, started at 2026-09-17T22:38:54Z using source
checkpoint `979f98ef`. `launch/observation.json` records the time-scoped live
scheduler and log observations, exact startup copies and source-map binding.
No completed-run or full-benchmark PASS is claimed. Keep source fixed while
this campaign measures; the same overnight automation follows it every15min.

`startup-telemetry-01/` is the single disclosed external120s observer window:
120samples, actual observer36540exit0, wrapper48732exit0, tree verified by the
owned wrapper, both query handles closed and all API groups successful. CPU
priority is NORMAL32 and memory priority3 for both host16220/editor13024.
Available RAM spans0.91–2.21GiB and system commit95.33–96.65% of its limit.
RSS/private commit both vary and page-fault counts rise; this does not isolate
hard faults, establish trimming causation, reconstruct old attempts or change
any benchmark baseline/gate. Exact byte values and artifact hashes are in
`summary.json`. Sampling is sequential and its overhead is not calibrated.
The read-only investigator cross-checked the small capture independently;
this is supplemental analysis, not an acceptance critic verdict.

The startup collector initially invoked nested Windows PowerShell where
`Get-FileHash` was unavailable. Its failure was retained and only the read-only
status query retried in the configured shell. A separate metadata assertion
caught use of canonical JSON instead of the existing source-closure domain
(sorted path + NUL + digest + LF). Identical partial copies were retained and
the metadata calculation corrected; neither incident restarted the workload.
