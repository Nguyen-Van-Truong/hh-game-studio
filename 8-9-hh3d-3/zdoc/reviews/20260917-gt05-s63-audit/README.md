# GT-05 S64 candidate

This package requests independent review of the original fixture pipeline and
protected **staged snapshot** publication. It does not activate an editor/game,
expose a public ACK, accept arbitrary artist input, or accept GT-06–GT-10.
GT-01–GT-04 are already accepted; their signatures do not apply to this candidate.

## Tested result

- Full pipeline suite: **233 run, 232 passed, one explicit Windows symlink
  permission skip**, zero failures/errors. `gt05-units-s64-02`.
- Native protected-storage matrix: **11/11**, including seven actual child
  deaths with exit 86, Stop and write failure. Each case preserves the preceding
  completed snapshot graph. `gt05-snapshot-native-s64-02`.
- Actual asset publication: complete strict chain recomputed, four real payloads
  published/read back, exact same-owner retry, read-only reopen and cross-owner
  command replay without repeating verification. `gt05-publication-s64-02`.
- Blender repeat exports have the same GLB bytes; the deliberate crate edit
  changes geometry/semantic signature. Python admission and pinned Khronos
  validation pass. Godot actually imports and reimports, reads 12 meshes,
  12 bones, 792 pose samples, 2160 skin vertices and two clips, preserves authored
  script/socket/material override, and captures 68 PNGs with nine draw calls.
- 27 deliberate bad observations are rejected at their intended check sites.
  Coordinator inspected nine bound images; independent critics must assess the
  evidence themselves. Art is minimal original test art, not final game art.

All final S64 unit/storage/publication lanes bind the same **143-file source map**.
The source closure is
`c141d54b80022ca7fefdf81f83e7e1078d3cc6aa43954831f82bb3178338a135`.
Native component lanes predate the final integration run; their complete
per-stage source maps are checked against the current frozen bytes by
`pipeline/verify_run.py`. No engine rerun is inferred from a new document/hash.

## Evidence and domains

The folder retains its S63 development name; this S64 manifest and selected run
IDs identify the final candidate. Native nav-path readback and actual Blender
bone rename/delete rejection supplements close the gaps found in initial review.
The log guard now rejects `Error: message` without rejecting benign counters.

`manifest.json` contains three independent, explicit inventories. Each digest is
SHA256 over sorted UTF-8 `path + NUL + per-file-sha256 + LF` records:

- `source_files`: outer Git repository-relative paths, full tested source.
- `review_files`: outer Git repository-relative exact governance snapshots
  (AUTHORITY=0), dependency acceptance receipts, this README,
  requirement coverage and package verification tools.
- `raw_files`: studio-relative paths under `.local/reviews`; the strict chain's
  723 local artifacts (the other 47 source reads are in `source_files`) plus
  the final unit/storage/publication captures, STAGED/bone supplements and
  coordinator visual review. Original local bytes remain authoritative.

The **manifest's own SHA256** binds all three inventories and run IDs. Critics
must record it and all three closure hashes. Reports/result JSON are outside the
frozen inventories to avoid self-reference. No absolute host paths or usernames
are copied into the committed inventory. Raw logs, generated assets, private
storage and images stay local; this is not a claim that Git alone ships those
bytes. Missing local evidence must fail verification.

The publication provider uses a different, labeled source-map JCS digest. The
receipt hashes the canonical JCS publication manifest; the observation hashes
the exact pretty JSON report bytes. Neither equals the sorted-path domain by
definition; the verifier compares the underlying maps/bytes in their own domain.

## Reproduce the verification

From the outer repository root, without launching any engine:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt05-s63-audit/verify.py --git-ref HEAD
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt05-s63-audit/test_verify.py
```

Before the checkpoint, use `--git-ref index`. The verifier checks each frozen
Git blob as well as the disk/raw bytes, and parses process/marker/result bindings.
`freeze.py` is a one-time inventory builder; it refuses to overwrite a manifest.
Native runner commands and source snapshots are captured in each indexed run.
Reruns require fresh IDs, preserve old attempts, and must not overwrite evidence.

## Limits and intentionally separate work

The native storage fault matrix uses synthetic payloads; actual asset validation
is proved separately by the full-chain publication, not by synthetic success.
In-memory tests cover every artifact/STAGED transition and readback failure;
native death cuts cover INTENT, first artifact, manifest, SELECTING, selector,
before terminal witness and witnessed terminal. A separately hash-bound STAGED
supplement adds actual death after durable STAGED, prefix reread, absent selector,
UNKNOWN and unchanged last-good bytes. No power-loss hardware test is
claimed. A missing terminal witness remains UNKNOWN/held, not auto-committed.

Two native Blender cases rename/delete `bn_head` in owned trusted source copies,
save/reopen and reach the installed admission check. Both reject exactly
`OBSERVED_NAME_SET` before export/publish, with GLB-derived affected consumers,
proposed old-to-new/null mapping and no accepted automatic migration.

Storage creates fresh immutable files within an owned local protected root,
using the accepted GT-02 primitives. It does not move a caller-supplied path across
volumes or replace an active asset. Process-loss recovery and sharing assumptions
are distinct from hardware durability. Active release/Windows-Linux/Android,
package installation, human usability and end-to-end client conformance remain
in their later gates. See `requirements-s64.md` for precise coverage and limits.

Preserved failures include missing test snapshot dependencies and the initial
visual endpoint comparator error. They are diagnostic history, not acceptance
evidence. Only the IDs in the frozen manifest select this candidate.
