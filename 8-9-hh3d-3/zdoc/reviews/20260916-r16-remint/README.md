# GT-01 deterministic remint preflight (r16)

`remint_plan.py` is a read-only preflight for the one official GT-01 runtime
remint. It verifies the frozen source-closure manifest against the current
tree, checks both Godot binaries against `studio/toolchain.lock.json`, and
atomically reserves the remint package so a concurrent invocation fails. It
does **not** launch an engine, install anything, tick the plan, or overwrite
evidence. Any source/lock/binary drift returns `GAP` (exit 2).

Run from the repository root, supplying the pinned console and GUI binaries:

```text
python 8-9-hh3d-3/zdoc/reviews/20260916-r16-remint/remint_plan.py `
  --manifest 8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/source-closure-manifest.json `
  --godot-exe <absolute-path-to-Godot_v4.7.2-stable_win64_console.exe> `
  --gui-exe <absolute-path-to-Godot_v4.7.2-stable_win64.exe> `
  --output 8-9-hh3d-3/zdoc/reviews/20260916-r16-remint/remint-plan.json
```

The output uses `<PRODUCT_ROOT>`, `<GODOT_CONSOLE>`, and
`<NEW_EVIDENCE_DIR>` placeholders so host paths never enter evidence. The
derived identifiers are deterministic for the frozen closure:

```text
run_id    = GT01-R16-<first-12-closure-hash>-OFFICIAL-01
command_id = cmd.gt01.remint.r16.<first-12-closure-hash>
```

After the serial runtime has completed and captured a real host exit, run the
exact binder command emitted in `post_run_binder_command`; its template is:

```text
python 8-9-hh3d-3/zdoc/reviews/20260915-r15-evidence/evidence_binder.py `
  --source-manifest 8-9-hh3d-3/zdoc/reviews/20260915-r15-closure/source-closure-manifest.json `
  --runner-output <NEW_EVIDENCE_DIR>/official-evidence.json `
  --repo-root <FROZEN_REPO_ROOT> `
  --output <NEW_EVIDENCE_DIR>/binder-result.json
```

`READY_FOR_SERIAL_RUNTIME` and the binder's `READY_FOR_CRITIC` are candidate
states only. Two independent read-only critics and coordinator acceptance on
the same frozen source hash are still mandatory before GT-01 can be ticked.
