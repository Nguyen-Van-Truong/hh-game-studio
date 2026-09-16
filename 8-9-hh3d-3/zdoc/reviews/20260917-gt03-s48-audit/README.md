# S48 diagnostic checkpoint — not GT-03 acceptance

AUTHORITY=0. Current progress is in the tools plan. This package does not issue
a public script, save or execution capability and has no formal critic verdict.

Frozen source closure:
`096239b1035bfcce0cb4cecf3251392d837cdaea66800428d920a7f4a5c462a5`
(74 files). Native Windows editor and Linux diagnostics use exactly this same
source map. Host/core and shared protocol retain the accepted GT-02 bytes.

| Requirement slice | Observed evidence | Limit |
| --- | --- | --- |
| Project CAS | 22 contract tests; actual shared Request projection | Host dispatch/IPC still absent |
| Immutable bundle | 19 tests for both content blobs/revision | UID/config/addon closure not published |
| Publication history | 31 reducer tests, 19 native journal tests | Stored engine/blob facts remain attestations |
| Real editor/UndoRedo | 103 edit checks, 10 reopen checks, 31 contract checks | Trusted fixed scene/script only |
| Script preservation | Attached source hash and exported value survive Undo and reopen | Generated UID retained in evidence; no multi-file commit |
| Evidence rejection | 17 editor and 10 Linux evidence tests | Diagnostic provenance, not an engine trust boundary |
| Linux executor policy | 12 pure policy/lifecycle tests | Not hostile-input runtime proof by themselves |
| Linux runtime | 11 actual confined fixtures, exact container cleanup | Full sandbox/validation acceptance remains false |

Total Python suite: **130/130**, no failures/errors/skips. All three native
editor lanes and the suite have actual exit 0, wrapper exit 0 and clean owned
trees. Full semantic scene revision matches after a separate editor reopen.
Source, snapshot and pinned binaries were unchanged. Results:
`../20260917-gt03-s48-editor-02/` and `../20260917-gt03-s48-linux-02/`.

The Linux fixtures observe real syntax/type rejection, `@tool` entry,
read-only source/root and network restrictions, full 16 MiB tmpfs, bounded
stdout, and owned timeout termination. Static initializers actually run in
`--check-only`, including non-tool input; the static busy fixture is terminated.
A script can print a forged validation result and exit 0. Its output remains
untrusted and `public_ack=false`; this is a demonstrated attribution gap,
not a validation success. The container configuration uses a pinned local
Linux image, read-only binds/root, no network/capabilities, non-root user,
no-new-privileges, bounded tmpfs/shm, 1 GiB RAM/no swap, one CPU, 64 PIDs,
resource ulimits, 256 KiB per captured stream, and a bounded owned watchdog.
The boundary audit records remaining limitations separately.

## Retained diagnostics and corrections

* Editor-01 passed 129 tests and the same 144 engine checks under its earlier
  closure. It is not assigned to the final source after the EOF regression.
* Linux-01 observed 8/9 fixtures. The 3-second busy-tool cutoff occurred before
  the callback marker, so it proved only startup timeout. Its actual exit 137
  and cleanup are retained. The corrected 10-second fixture observes callback
  entry before timeout. Linux-02 adds two static-initializer cases.
* Linux startup run-01 had a host Job-accounting settle false alarm; run-02
  added bounded drain. Both records remain. No unrelated container was removed.
* Journal diagnostic runs 01–04 retain their source limits. Run-01 has no
  reconstructed source manifest; final combined snapshot supplies complete
  provenance. Cached reducer import was bound to path+hash; native root owners
  are freshly checked; invalid digest retries reject without disabling Stop.
* Cross-review caught saved verdict/incomplete artifact-map trust and raw-case
  transplants. Resume now rebuilds verdicts from raw observations, exact input
  bytes/mode/deadline and complete artifact inventories. Reader failure/EOF,
  actual host/container exit, source closure and provenance are checked.
* Initial evidence unit fixture counts were still 97/7/28 after adding script
  checks. The three failed count assertions were corrected to 103/10/31 before
  the frozen run; no product behavior was changed to satisfy those assertions.

## Reproduce / verify

From the HH3D directory, use **new** output paths and run IDs after a source
change; `--resume` is only for identical frozen source and completed case files.

```powershell
python -B studio/tests/godot/run_editor_probe.py --run-id NEW_EDITOR_ID --output zdoc/reviews/NEW_EDITOR_DIR
python -B studio/tests/godot/run_linux_probe.py --run-id NEW_LINUX_ID --output zdoc/reviews/NEW_LINUX_DIR
python -B zdoc/reviews/20260917-gt03-s48-audit/verify_evidence.py
```

The verifier checks both source closures, raw native process records, required
engine checks, exact script/project vectors, Linux created/exit/removal
observations, confinement configuration, captured output bounds and artifact
hashes. `index`/`HEAD` arguments also compare bytes reconstructed from Git.
The manifest preserves previous diagnostics and reports without treating them
as final evidence. Source changes intentionally invalidate current-source
verification of this checkpoint; retain the historical frozen copies.

## Next implementation

Authenticated effect-time authority, actual blob staging/selection/readback,
full project/UID closure, owner restart and Stop/crash recovery still need
integration. A closed declarative script profile is a proposed first supported
profile; it still requires real confined parse/import and fresh trusted
instance/hash readback. Arbitrary callback/static-initializer inputs remain
unsupported for activation. Two independent critics must review the complete
GT-03 closure before coordinator acceptance.
