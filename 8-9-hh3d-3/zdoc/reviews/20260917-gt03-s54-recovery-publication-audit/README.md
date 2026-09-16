# Frozen authenticated recovery component verification

PASS for the captured run `GT03-S54-RECOVERY-PUBLICATION-01` only. This is implementation component verification, **not an independent GT03 acceptance critic**. No acceptance signature or plan tick is supplied.

The frozen source closure is `469b22d6788ef63c7ca4d6e7dc91e703494db439834dffacdef7d476a9464bdc` (168 files). The original checkout changed during the run (`origin_source_unchanged=false`); the frozen copy is byte-exact. Later V5 and Undo/Redo work cannot inherit this proof. `live-source-delta.json` is an observation of later checkout differences, not an acceptance input.

Verified chain:

1. The actual Linux container parsed, imported, and read back the initial managed fixture. Each raw phase exit is 0; raw Docker wait and exited-state inspection agree. Container ownership, read-only mounts, bounded PID1, command Job cleanup, and actual removal are recorded. Both isolated input trees match all 11 selected file hashes. The actual semantic snapshot binds to the original editor and the native bootstrap manifest.
2. A real authenticated HTTP `scene.save` reached the owned Windows EditorPlugin capture. The native capture observation and 266-byte scratch scene match the crash record. The protected original command remains `CAPTURE_PREPARED` with no original response. The original host actually exited 92; its wrapper exited 0 and captured its owned Job tree as clean. Its original Godot process has no graceful exit receipt after this intentional crash.
3. A fresh HTTP recovery session used fence 2 after the original fence 1. The frozen harness records denial of a read-only grant, fresh-editor reconciliation, exact lookup, duplicate retry, and fresh HTTP host reopen/retry without another editor or event. There are **14** captured harness assertions, not 15. No independent packet transcript is present.
4. The durable stream is exactly nine records: genesis, three bootstrap records, `CONFIG`, `CAPTURE_PREPARED`, `ADMITTED`, `READBACK`, `TERMINAL`. The Registry witness equals the final native head. The native root/stream identities, original selector FileID/hash, manifest, and all 11 selected file versions agree with the frozen exports. Selected project bytes remain unchanged.
5. The fresh editor uses generation 2 and a different session/PID/creation time/root identity, reads the initial last-good state, and has no Undo/Redo history. Its actual exit and wrapper exit are 0 with a closed, empty Job. The terminal response is byte-exact `REJECTED / GODOT_RECOVERED_LAST_GOOD`, with `files_saved=false`, `restored_editor_history=false`, and `public_ack=false`. The original interrupted save is not relabeled successful.

`capture_native.py` made a read-only native export using the frozen accepted Registry, protected-file, and event primitives. It did not open RecoveryJournal, attach custody, append events, rearm, or provision anything. Registry and stream bytes were unchanged across the observation, and every retained native resource closed. Export checksums detect damaged evidence; they do not replace Windows ACL authority on another host.

`verify_package.py` independently checks raw process/container artifacts and native frame chaining, then replays the frozen pure publication/recovery folds. It recomputes both editor and validation runtime release digests. Its 20 in-memory corruption cases all reject, including stale fencing, forged editor generation, altered prefix, and forged success at the typed suffix fold. No engine, Linux container, transport, or native custody is opened by this verifier. No original evidence is mutated by its negative cases.

This case starts with an unchanged initial scene and interrupts before the durable captured event. It does not prove recovery of a prior edit/UndoRedo stack, V5 interrupted edits, original UNKNOWN, post-CAS recovery, orphan COMMITTED, durable Stop, or GT07 restart. Other component evidence remains separately scoped.

## Reproduce the audit without engines

Keep this directory and sibling `20260917-gt03-s54-recovery-publication-01` together. The paths in `portable-manifest.json` are relative to their common `reviews` parent. From the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s54-recovery-publication-audit/verify_package.py
```

Expected: exit 0, `passed=true`, 168 source files, 14 harness assertions, nine native records, 11 selected files, and 20 tamper rejections. The verifier reads the frozen source only after validating its full closure and checks every portable artifact against the stored manifest. It does not rely on the newer live checkout. Python optimization (`-O`) is unnecessary; verifier checks use explicit exceptions.

The manifest excludes generated `.godot`, Python cache, AppData/LocalAppData,
temporary files, protected live `storage/` roots and its own bytes. S54 checkpoint
curation corrected the initial 317-file inventory, which had included unused
private storage files. The verifier uses the explicit read-only native exports;
those exports and every verification input remain included. This correction
does not change the runtime evidence or require another engine run.
Preserve the published manifest hash as the external integrity anchor. `--write`
is reserved for rebuilding this audit's records after an authorized audit change;
ordinary verification uses no write option. `capture_native.py` is an
already-completed Windows observation script, not part of portable replay.
