# S82 full-sequence object attribution

AUTHORITY=0. Diagnostic only; never an eligible campaign sample or acceptance.

The S81 frozen source remains at `b3862a10`, 51 files with closure
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.
Profile remains `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
Read the exact `diagnostic.json` profile digest in the raw run for verification.

`diagnose_sequence.py` calls the unchanged campaign `run_child` and
`screen_sample`. Its only override is preparation of a disposable native plugin:
collect a reachable-object baseline at ACK4 and a second inventory if the joint
ObjectDB count rises. The second inventory is flushed before the ACK marker, so
the original gate's immediate failure cleanup cannot discard it. All original
35-batch, 1000 HTTP-command, 100 native-cycle, source, Stop and ownership checks
remain active. Only one process pair is launched; there is no campaign assembly.

The probe is a partial reachable inventory, not a full ObjectDB census. Its
primitive descriptors do not retain Object references, but its allocations and
collection time affect RSS and timing. A failed timing/RSS gate must remain a
failed diagnostic observation. A successful diagnostic cannot enter the official
dataset: the run has an explicit effective-source overlay and no campaign or
assembly manifest. Do not turn a nonreproduction into a root-cause conclusion.

The collection helper derives from the S82 native-only probe. It additionally
records baseline ID/class pairs and per-owner TreeItem counts. A post-publication
counter check fails closed if the probe itself changes the ObjectDB count.
The copied native plugin hash and base source hash are separate in
`native-overlay.json`; the editor owner's effective source map also includes
the copied plugin. The host owner binds all 51 base files and both helper files.
The native `full` mode is used only to retain the original sequencing/gates;
outer metadata explicitly sets `eligible_for_dataset=false` and
`full_benchmark=false`.

Raw outputs under `studio/.local/reviews/`:

- `gt06-s82-attribution-preflight-01`: initial owned import, superseded helper.
- `gt06-s82-attribution-preflight-02`: final owned import with both review fixes.
- `gt06-s82-attribution-01`: one bounded instrumented HTTP/native sequence.

Final preflight completed with native PID28016 exit0, wrapper0, natural tree exit,
Job zero/closed, stderr empty and no benchmark activation. This proves parsing
and import only; runtime attribution has not been proven by that preflight.

Use the fixed `--preflight` entry only once. After preflight byte verification,
launch the fixed `--supervisor` using Python's windowless companion. The parent
owns a checked campaign-host Job and uses the existing bound `stop-request.json`
contract; it never terminates unrelated processes. Its return record is not its
actual process exit. Inspect child/helper actual exits and all cleanup receipts.
Maximum wall time remains7410s. Do not restart or overwrite this run ID.

Expected first useful observation is baseline ACK4; the old failure appeared at
batch15 after about31min. That gives a check interval, not a prediction that the
same fault will recur. If no fault recurs, this diagnostic may run all35batches.
