# GT04 retained cleanup and durable internal response candidate

Candidate only; public_ack=false; no formal acceptance. Frozen run
`../20260917-gt04-durable-01/` has source closure
`820c6d7a955a0addb814f66935a7fc1471cb58ce17e355505c134b846840edb1`.
It passed 103 Python tests, 13 native cleanup checks and 16 native durability
checks. Both captured target/wrapper exits are zero with checked runner trees;
source and frozen copy stayed unchanged. No Blender remained after capture.
Earlier export04 and cleanup01 remain separate historical closures.

Two actual capped exports exercise normal completion and a checked Windows
CloseHandle fault before native handle closure. The fault happens twice; the
same native owner stays retained. The GUI closes while export cleanup remains
held, then a third attempt closes the exact retained Job after observing zero.
The original failed host-result remains byte-identical; numbered cleanup
attempts record failure/failure/success without promoting the export result.

The new private session uses unchanged GT02 Journal primitives for intent,
checksummed fsync terminal records, command digests and writer lease epochs.
Real Blender create/readback precedes terminal persistence. Duplicate requests
and lookup-only reopen return byte-identical original response bodies. Native
main-thread admission rejects old authenticated fences and rejects attempts to
lower its high-water mark. BUSY writers and expired/superseded leases cannot
introduce effects. One actual host exits74 after native create but before
terminal persistence: an independent retained process handle observes Blender
live then dead, and reopened pending intent stays UNKNOWN without dispatch.

The journal is a private internal fixture log, not a protected publication
custody store. COMMITTED here means a durable record of a native observation;
scene_state_durable=false is explicit. No public protocol ACK, FIFO writer
scheduler, automatic .blend scene recovery, artist-file parser sandbox, or
power-loss publication is claimed. Box-only material/rig limits remain open.
The proposed next profile in `studio/blender-addon/SUPPORTED_PROFILE.md` is
declared unimplemented. Two independent critics are still required.

Read-only verification (no engine launch or metadata writes):

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-durable-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-durable-audit/test_evidence.py
```

The default validates the named frozen closure even after later implementation
work changes live source. Add `--check-live` to require current source equality;
that extra check was green at this checkpoint. The observed native death exit
was zero: Blender may quit on IPC EOF before Job teardown. The evidence proves
owned process termination, not which of those two paths won the race.

Only explicit `--write-derived` writes this audit's portable manifest and
verification summary. It never edits source or original captures. The checker
reconstructs core journal history in memory and validates native raw markers,
process exits, exact receipts, retained handle attempts, source maps, GLB/input
hashes and orphan state. Portable artifacts exclude user/temp caches and guard
files. Audit tamper tests replace read bytes in memory only.
