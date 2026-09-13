# GT-01 gap audit r18 (read-only, 2026-09-13)

## Verdict

`GT-01=IN_PROGRESS`; `GT-02=PLANNED` remains correct. The current tree is
**WIP/dirty** (runner headed lanes + isolated user environment + fixture
plugin files, plus lifecycle probe). Therefore the R16 closure/evidence hash
`df94c50173d296f446438c3b1ba022982d9eacde67705c6d609ecfa6d0f0a6a0`, its
manifest, and both R17 `TICK=no` verdicts are historical and cannot be used for
acceptance or officialization. Do not edit a candidate field to `OFFICIAL`.
After the final source edit, all IDs and hashes must be reminted.

## Minimum gates still required

1. **Freeze and closure.** Stop source edits, generate a complete closure
   (including `addons/gt01_probe/*`, the headed/env runner changes, and any
   lifecycle helper/tests), verify regular/non-link files, paths, duplicate-key
   rejection, no secrets/host paths, and record closure plus manifest hashes.
2. **Pin/provenance and scoped recovery.** Verify the pinned Godot archive and
   detached SHA512 row against the lock; record the real bytes-only receipt and
   local install/activation/cache isolation. Run the GT-01-scoped lifecycle
   cases (candidate/cache isolation and cooperative live-owner/crash/CAS
   observations) once and bind their report/log hashes to the same frozen
   closure. Do not pull GT-10's full migration/upgrade/downgrade/uninstall
   acceptance into GT-01.
3. **One serial official runtime remint.** On the frozen source, run the
   headless import + check-only + trace lanes and the real headed editor + GUI
   trace/capture lanes through the menu path. Capture host/wrapper exits,
   `(pid,start_time,root)` ownership/leftovers, clean stdout/stderr, trace and
   capture postconditions, isolated Godot user-data paths, and all per-log
   hashes. A `PASS` banner or exit 0 alone is insufficient; never run a second
   worker on the same fixture path.
4. **TQ01/TX12/TX14 binding.** Produce fresh evidence (Unicode/space root,
   no PATH/system mutation, cache isolation, quota/network/auth/Stop semantics
   that are explicitly GT-01 slices) and bind it to the exact closure/runtime
   identities. Synthetic/offline checks remain supporting evidence, not a
   substitute for the official package.
5. **Binder then critics.** Binder must independently return
   `READY_FOR_CRITIC` with non-null closure/evidence/log hashes. Dispatch two
   isolated read-only critics with identical source/manifest/evidence/run/
   command hashes; accept only explicit matching `TICK=yes`. Coordinator then
   re-runs static/runtime/closure checks, writes adjudication, updates one plan
   row, and commits. Any byte change invalidates the package and critic votes.

The R17 demand for a **full** installer recovery/migration suite would be
scope creep: plan TX12 assigns GT-01 only candidate/cache isolation, while
full ABI/template/build is GT-08 and full migration/rollback/uninstall is
GT-10. Likewise, substantive TX14 journal/token/Stop recovery belongs to
GT-02/GT-07/GT-10. The current `GT01_PENDING=TQ01_TX12_TX14` wording therefore
contains the known cross-WP acceptance-cycle risk (r10 P0): coordinator should
make the GT-01 gate machine-checkable with only executable smoke slices
(cache isolation, bounded Stop-before-reconnect, no fallback/secret echo), and
mark deferred TX12/TX14 rows as blockers for their owning later WPs. A narrow,
closure-bound archive verifier plus lifecycle/CAS probe is still needed because
archive/recovery are explicitly pending in the GT-01 status. The
candidate-to-official transition is intentionally sequential (runner
candidate -> frozen closure/binder -> two critics -> coordinator); this is not
circular acceptance and must not be shortened.

## Reuse versus rerun

- **Reusable as immutable inputs:** the locally verified Godot 4.7.2 archive
  bytes and detached sums, export-template archive hash/metadata, and Blender
  5.2.1 archive/binary can be reused if their lock fields and bytes remain
  unchanged. Re-emit fresh verification receipts in the new package; the
  export templates remain `ARCHIVE_VERIFIED_NOT_INSTALLED` and are not a GT-01
  runtime gate.
- **Reusable as test material only:** r11 lifecycle candidate, r13/r16
  headless logs, r14 TQ candidate, and S20 headed/Blender partial logs. They
  are candidate/partial, use older source closures, or lack binder identity;
  do not copy them into an official package. Their fixture scripts and test
  patterns can seed the remint.
- **Must rerun after this WIP freeze:** Godot headed/editor and GUI capture
  (the plugin/env changes are new), all three headless lanes, Blender fixture
  save/reopen and overwrite-rejection if claimed in GT-01 evidence, lifecycle
  report/logs, and TQ01/TX12/TX14 checks. Rebind every output to one new
  closure hash; do not reuse R16 IDs.

## Pending source-risk headings for coordinator

- `run_fixture.py`: `--headed` currently launches the console binary variable
  even though the GUI companion is only hash-checked; launch the pinned GUI
  binary for editor/window lanes. It also records `trace_lines` from headless
  only, while headed trace adds capture metadata; binder compares each lane's
  reported trace exactly, so record independent headed trace data (or make the
  contract explicitly per-lane). Emit `artifact_hashes` for `menu.png`; the
  binder requires exactly that capture path/hash. Ensure headed failure cannot
  be silently downgraded and every lane has independently hashed host/stdout/
  stderr.
- `_isolated_user_env`: verify Godot actually resolves editor data/cache under
  the per-run roots and that directory creation/ACL/reparse checks are safe on
  Windows. Godot documents Windows editor data under `%APPDATA%\Godot` and
  project `user://` as writable; see [file paths](https://docs.godotengine.org/en/latest/tutorials/io/data_paths.html).
  Setting `APPDATA` is plausible but must be observed in runtime, not inferred;
  avoid treating `HOME`/`USERPROFILE` overrides as proof of isolation.
- `addons/gt01_probe/plugin.cfg`: Godot editor plugins conventionally live in
  `res://addons/<name>/`, with `plugin.cfg` plus a tool script; the relative
  `script="probe.gd"` is consistent with the official [Making plugins](https://docs.godotengine.org/en/stable/tutorials/plugins/editor/making_plugins.html)
  layout, but headed runtime must prove the plugin is enabled and emits one
  `GT01_EDITOR_TRACE` postcondition on the real window. A project setting alone
  is not proof of execution.
- The current dirty source means any closure/critic hash written before these
  files settle is stale. Keep one writer and no concurrent Godot/Blender run.

`EXECUTED_TESTS=false`
`GT01_ACCEPTED=false`
`GT02_OPEN=false`
