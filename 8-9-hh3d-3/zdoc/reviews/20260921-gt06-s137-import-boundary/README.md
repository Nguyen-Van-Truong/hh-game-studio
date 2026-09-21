# S137 import-boundary review

Authority 0, diagnostic only. The three independent reviews in this folder
correct the S134/S135 evidence wording and design a bounded attribution step.
No Godot, Docker, benchmark, test, source, profile, gate, timeout, baseline or
RSS policy was changed. No acceptance dataset was produced.

S135 did run a Godot process through parse and import; the import child returned
`-9`, the Python phase driver then returned `45`, and readback/command work was
not reached. The managed repair lane failed before command/owner creation with
`VALIDATION_PHASE_ORDER`; its owner/transport cleanup is a narrower claim than
engine cleanup. `OOMKilled=false` and closed jobs do not identify the signal
sender. `RLIMIT_CPU=10` is a testable hypothesis, not a root-cause finding.

The next permitted action is read-only static comparison first. Only if that is
clean may one fresh authority-0 observer/control diagnostic be run, preserving
the exact source/profile/workstation and original gates. It must capture actual
host/container exits, Docker events and owned cleanup, and fail closed when any
required evidence is missing. It cannot become F13/F14 or a formal GT06 pass.

`static-diff.json` is the derived D0 comparison of the two S135 probes; it
classifies the boundary as `IMPORT_CHILD_OR_LIMIT_UNKNOWN` and does not infer a
sender. `metadata-correction.json` records the packet-custody, stale/circular
digest, phase, and cleanup-scope corrections without rewriting the preserved
packets.

The bounded D1 exact-profile observer then completed parse/import/readback with
exit 0, no timeout/OOM, clean owned job teardown and unchanged input. The D2
inert control initially failed before process start because its read-only bind
was missing the stock `.godot` mountpoint; that raw attempt is preserved. Fresh
D2-02 then emitted both sentinels, exited 0, waited 0, removed 0 and inspected
as exited without OOM or kill events. `d1-d2-summary.json` records both runs;
neither is a formal GT06 sample or an attribution of the earlier `import -9`.
