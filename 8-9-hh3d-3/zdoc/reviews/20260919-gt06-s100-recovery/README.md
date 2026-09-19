# S100 recovery: import timeout and focused latency diagnosis

AUTHORITY=0. GT06 remains IN_PROGRESS. No benchmark PASS or critic verdict.

The S100 campaign failed before batch zero. The trusted import wall limit is
20 seconds and the captured elapsed duration is 20.203 seconds. The supervisor's
63.984 seconds includes other preparation; it is not the import deadline.
Only the Godot banner was captured. The exact startup stall is not identified.
S98 imported the equivalent initial project in 4.765 seconds; only the inert
run ID differs. S97 imported in 4.578 seconds but includes a diagnostic overlay.

`failure/manifest.json` seals 151 exact local copies, SHA256
`4b645aa18585f0878ac9ac868215c5bf3b9ba00b1043767a2dfe62ed32c64e51`.
The import Job and host Job drained and closed with no retained handles.
Import natural exit is UNKNOWN, helper exit is 2. Host actual exit is 1.
Do not substitute these values for each other. `scheduler-terminal-01.json`
records scheduler state3/result1/no instances and a fresh query with no live
supervisor/host/import PID. Neither absence nor scheduler state recovers the
missing natural exits. `scheduler-retired-01.json` is a later supplement.

Source51/profile remain fixed. `source-stop-check-01.json` verifies all current
runtime bytes and absence of Stop in all 30 fixed attempt slots. Call
`campaign.load_fixture()` before collecting the dynamic source map: otherwise
three non-imported fixture dependencies are absent from the map, which is not
source drift.

The exact-copy manifest includes the small generated `.godot` diagnostic file.
It stays local and is excluded from Git. `portable-inventory.json` records the
Git-eligible exact files separately; its domain does not replace the local raw
manifest. Journal copies, run caches and credentials are also excluded from Git.

Independent implementation lanes (not acceptance critics):

- `hash-reader-probe/`: streaming SHA512 measurements on a disposable exact
  S98 journal copy; preserves original bytes. Small warm-cache improvements
  cannot explain a 2-second lookup timeout or justify a PASS claim.
- `http-attribution/`: short copied-history HTTP probe, unchanged runtime,
  with bounded timing of verification/locking/durability and first lookup
  failure. Root serializes launch; no concurrent engine or microbenchmark.
- `import-attribution/`: one cold import with unchanged native arguments,
  source and 20-second Job deadline; observation only. A successful diagnostic
  would establish only non-reproduction, not a repaired root cause.

S99's 35-batch command-only diagnostic completed in 4707.391 seconds without
reproducing the coupled timeout. Batch durations grew with journal length;
the normal verified path hashes every byte under the host lock. Another long
uninstrumented run provides little new information. The next decision must be
based on phase evidence, then a narrowly scoped fix and affected validation.

`s98-preflight-errata.json` corrects pagefile labels without modifying the
original snapshot. Microsoft documents Win32_PageFileUsage sizes in megabytes,
not kilobytes: https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-pagefileusage
The missing committed-bytes value stays unavailable. The snapshot was collected
after termination and cannot attribute the earlier failure to memory pressure.

The prior S100 plan is archived verbatim with hash and AUTHORITY=0. S101 in the
main tools plan is current. Preserve all previous failed attempts and original
thresholds; no partial samples enter F13/F14. GT07–10 remain gated by GT06.
