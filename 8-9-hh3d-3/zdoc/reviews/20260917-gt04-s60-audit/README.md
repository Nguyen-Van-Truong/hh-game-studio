# GT04 S60: external-reference admission repair

**CANDIDATE; GT04 is not accepted and GT05 is not open.**

S59 review was interrupted before final verdicts. Preliminary independent
findings were then reproduced by the coordinator. No S59 signature, test result,
or acceptance is transferred to S60. Astra review attempts hit service capacity,
and a fallback stream disconnected. Latest owner reauthorized two independent
Codex Astra extra-high critics on this frozen candidate and a separate GT05
readiness agent. No final verdict is available. This component proof is not review.

Source: **140 files**, closure
`f5ae5dfbb451d3204197c2b21486c586698089ac24d14d23641a9182b5e42673`.
Native matrix execution closure:
`407fff4e453fb1702a32fbc8ae1ee5eff7c3dcb0b99338a504ae39dc69d67824`.

## Changes and verification

Unsupported Blender libraries and images now reject before reading filepaths,
resolving Blender-relative paths, or probing the filesystem. Export preparation
checks scene revision/context before exporter preflight. Existing/missing,
packed/generated, UNC/device/relative/absolute references grant no intake.

- Five new unit regressions cover forbidden path access and stale preconditions.
- Full Blender units **599/599**. Checkpoint/export focused units **328/328** each.
- Three real HTTP/native file profiles each pass **49 client checks / 36 calls /
  10 native checks**, with actual GUI/export/client/host exits and owned Jobs.
- Full S60 native matrix **17 lanes / 240 top-level checks**, including UI edit,
  material, IPC, cleanup retry, leases/FIFO, checkpoint, deadlines, five crash cuts
  and four Stop cuts. All use the same S60 runtime; no old result is relabeled.
- Native IPC and material probes each reject existing/missing libraries and
  images while `Path` and `bpy.path.abspath` are blocked: **six checks** in
  `native-no-external-io.json`. No test reaches a real external host.
- File-only audits pass for all three profiles and the full matrix. Audit
  corruption tests: **15 negative cases plus one empty-stderr regression**.
- Evidence-view tests: **12/12**, including raw/view tampering, missing empty
  logs, metadata scope falsification, unregistered paths, binary omission and
  traversal. A portable integrity check never claims exact raw verification.

The only cleanup was seven generated `.pyc` files after every native lane
completed; `generated-cache.json` records their hashes and relative paths.
All 140 pinned source files stayed unchanged. No unrelated process was stopped.

## Raw evidence and the committed view

Raw S60 packages stay immutable under `studio/.local/reviews/`, indexed by
`verify_views.PACKAGES`. They contain native process launch paths and are **not
committed**. S59 raw history remains unchanged and is not a conforming S60 pack.

`portable/` is an explicitly transformed explanatory view. Each manifest stores
both original and view hashes, transformation mode, and byte lengths. Native
source/binary/cache files are hash-only: silently editing `.blend` bytes to
remove metadata would destroy their artifact proof. JSON numeric results,
receipts, IDs, exits and native assertions remain intact; known local path roots
become `$PROJECT`. Unregistered host paths or personal values stop packaging.
These checks address path privacy for the current fixture, not arbitrary secret
detection. Existing session-secret checks remain in the raw integration audits.

The source-closure manifest records source hashes available from Git. Original
artifact hashes inside receipts remain in the **raw** domain; a sanitized log
does not become the original log, and a view of a journal is not recovery input.
`review-closure.json` binds both the portable Git files and all retained local
raw hashes. Git verification covers the portable/source files only. Reviewers
on this workstation can verify the original process and binary evidence; a
clean checkout can verify the committed view and regenerate fresh runs, but
cannot claim to possess the old raw bytes. This limit must be assessed by the
two final critics; no coordinator self-review substitutes for that decision.

The clean Git reconstruction in `clean-checkout.json` restored **909 staged
files** byte-for-byte. Portable verification passed without local originals;
the explicit raw-verification probe rejected their absence. Both bounded target
and wrapper processes exited zero with clean trees. This verifies the view's
portability and honest boundary, not native raw-byte reconstruction. The final
inventory adds this verification report and the updated explanatory metadata.

## Reproduce

From the repository root, with `python -B`:

1. `verify_views.py` checks portable byte integrity without local artifacts.
2. `verify_views.py --local-raw` checks original inventory plus every exact
   deterministic transformation. It must fail when any required original is
   absent or changed.
3. `verify_evidence.py scene`, `checkpoint`, `export`, and `verify_matrix.py`
   read the original local packages and test actual native/source binding.
   They write verifier copies/reports only under `.local/reviews/`.
4. `test_evidence_view.py`, `test_evidence_rejection.py`,
   `test_matrix_rejection.py` exercise the audit rejection paths.
5. `checkpoint.py index` or `HEAD` verifies Git bytes. `checkpoint.py check`
   verifies the full current review closure, including local raw bytes.

For a fresh native reproduction, use the pinned `run_writer_client_probe.py`
with the three fixed profiles, `--unit-suite all` for scene and `focused` for
the other two, then `matrix.py`. The run IDs and package paths are fixed in the
recorded recipe/source manifests; use a clean isolated checkout or a new
candidate namespace. Existing output is never overwritten. Fresh PIDs/timestamps
and generated binary hashes require a **new evidence closure**; they are not a
reconstruction of this run's original artifacts.

`public_ack=false`, `scene_state_durable=false`, and component-only scope remain.
Only the selected protected immutable bundle claims `durable_publication=true`.
Arbitrary artist-file intake, restored Undo/writable restart, cross-app activation,
Android, release packaging and HH World are not claimed by S60.
