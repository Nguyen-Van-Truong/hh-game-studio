# P3–P6 pre-review — `gt10pc-rehearsal-20261012-c3e`

Read-only audit of rehearsal package `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-c3e` (authority 0, `mode=REHEARSAL`, `acceptance=false`, `status=REHEARSAL_PASS`). Judged against **HEAD** `8-9-hh3d-3/studio/tests/conformance/` (`git show HEAD:...`). Working-tree WIP was read only to see whether a gap is already being closed. No Godot, Docker, matrix, or test suite was run. Hashes below were recomputed from the files on disk.

Fixtures in HEAD and in the package: **`gt09-arena`** (root `Node2D`, project id `project.registered.arena`) and **`gt09-room`** (root `Node3D`, project id `project.registered.room`). Constant: `run_gt10pc_matrix.py` `FIXTURES`.

Signed archives (bytes match `matrix.json` `artifacts`):

| target | version | archive sha256 | manifest sha256 |
| --- | --- | --- | --- |
| Windows | 0.1.0 | `af6356e3a61dcf723222b5c8a47c1d5c592bc4619906dd5263f9acaa9e0fdbab` | `85546002a7086f5a7e0e44edead5e0ecc7babcc70253e4d6481a8ccc54068e5b` |
| Windows | 0.1.1 | `ca1b09090748d9d1c62367ed4d9a7bf21104f252c5720070a172a772e6d665be` | `4c3c5e52c41d46d053f6d170823bf9b339a55e4bea1cb7d36aa482cc11a5de80` |
| Linux-headless | 0.1.0 | `e804a3cc32fbd9834dcf5e2d82da090fb528dc9d2fdaac9207f23b11a7e7ecf9` | `e9683c3370ba3810d89e0e0fbc687a2380216319126235ac8305331418366477` |
| Linux-headless | 0.1.1 | `342bbfd66e5bb1938c4aae146d064498532023e0dfb463b415dfb11e6dfc7453` | `ec98579afb1354edaec1af95d8927a3a802c9dc981a2db5d3355269a9a9521c4` |

`0.1.0` and `0.1.1` on both targets share `schema=hh-studio-package-0.1`, `protocol_schema_digest=53f820edc283f405c28b10d484a33f2d2d155446fecf1143354071da657e25cf`, `source_closure_sha256=a90f378e…`, and `rollback_compatibility={schema: hh-studio-package-0.1, version_series: 0.1}`. Fixture sprite `payload/studio/fixtures/gt09-arena/assets/sprite_sheet.png` is `c12d85bfa77cce4254ec9936e232f06257f62cd83bd9f8e70cce6c6a08bd9166` (14889 bytes) in every archive. Windows Godot pin in `toolchain.lock.json` `godot.console_sha256` is `c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643` (4.7.2-stable). Linux pin in `godot-addon/validator-toolchain.lock.json` is image `sha256:7e51d8b09fe7e3778402d55ca7bfd05a1a02cf4dbc4a7308b4a0b3cb607ae8e7`, context `desktop-linux`, binary `Godot_v4.7.2-stable_linux.x86_64`, `binary_sha256=8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e`.

`matrix.json` rows P3–P6 are only:

```json
{"linux": "REHEARSAL_PASS", "producer": "windows-producer", "status": "REHEARSAL_PASS", "target": "Windows"}
```

## What HEAD actually checks

Production (`run_gt10pc_matrix.run_rehearsal`) does deep-check once, then writes the flags:

- Windows: `_child(..., "windows-producer", run_gt10pc_native_probe.py)` then `verify_only(windows/)`. `windows/matrix.json` is schema `hh-gt10pc-matrix-2`, mode `DIAGNOSTIC`, so this call reaches `_verify_native_producer`. Task stdout line 0 is that verifier’s fixture/lifecycle dump.
- Linux: in-process `gt10pc_linux_producer.run_linux` then `gt10pc_linux_verify.verify_linux`. Not a `children/` subprocess.

Re-verify of the **package** does not repeat that.

- `verify_only` on a directory whose `matrix.json` is schema `hh-gt10pc-matrix-3` and mode `REHEARSAL` calls `_verify_rehearsal_matrix`. For every non-P11 row that function only requires `rows[row].status == "REHEARSAL_PASS"`. It does not read `linux`, `windows/`, `linux/`, or `children/`.
- `_verify_final_matrix` for P3–P6 only requires `target=="Windows"`, `producer=="windows-producer"`, and `linux=="FINAL_PASS"`.

So a later `--verify-only` of c3e trusts the producer-written PASS strings. The nested verifiers, **when invoked**, re-hash raw files:

- `_verify_native_producer`: `digest_file` of every `producer.json` `evidence` path (155 files; spot-check `consumer/gt09-arena/project-before.json` matches). Ledger JSON must equal fixture members inside the signed Windows archive plus save bytes `consumer-save-before-install\n` and manual bytes `owner edit must survive uninstall\r\n`. Phases must be `install`, `upgrade`, `rollback`. Each phase: `_process` (exit 0, wrapper 0, `tree_verified`, host pid/exit agree), `_lifecycle` on Godot stdout, `verify_profile`. It does **not** re-walk `consumer/*/project/`.
- `verify_linux`: same style for Linux ledgers (manual note is LF, not CRLF), plus docker host receipts, image inspect, container id, confinement, and four phases `install/upgrade/rollback/reinstall`. It requires post-exit `State.Pid == 0`.

WIP (not HEAD): untracked `gt10pc_matrix_verify.py` `verify_raw_rows` calls `_process` on `children/windows-producer-receipt.json`, `_verify_native_producer(windows/)`, and `verify_linux(linux/)`. The modified `run_gt10pc_matrix.py` routes `_verify_rehearsal_matrix` and `_verify_final_matrix` through `verify_matrix`. That closes the package-level PASS-flag gap only. It does not add an incompatible-schema case, a running-container PID, a host-env snapshot, a Windows reinstall Play, or a second on-disk project.

## Linux container (real run; not proved by the folder name)

Launcher: the matrix process inside the scheduled task (`…-c3e-task`, `return.json` `returned_exit_code=0`, elapsed ~1640s). `run_linux` calls `docker.exe` via `run_process` and writes receipts under `linux/host/`. There is **no** `children/linux-*`. `children/` for this slice is only `windows-producer-*` (exit 0, `target_pid` 13296, `wrapper_pid` 26180, host file agrees). Other children are P2/P7/P10.

Host-recorded docker CLI (`linux/host/*-receipt.json` equals `linux/producer.json` `processes`, and `*-host.json` pid/exit agree):

| label | exit | target_pid | what |
| --- | --- | --- | --- |
| image | 0 | 14032 | `docker image inspect sha256:7e51d8b0…` |
| create | 0 | 16212 | `docker create --pull=never` of that digest; stdout is the container id |
| inspect-created | 0 | 26260 | status `created`, `State.Pid=0` |
| run | 0 | 23168 | `docker start --attach 8e00bb21…` |
| inspect-exited | 0 | 27208 | status `exited`, `ExitCode=0`, `State.Pid=0`, not OOM |
| inspect-closeout | 0 | 20720 | still exited, Pid 0 |
| remove | 0 | 2888 | stdout is the same container id |
| leftover | 0 | 14588 | `docker ps` filter stdout empty; `owned_removed=true` |

Container id `8e00bb2101812b853a823fd687cdbd9b2971e0eceafea1aefe57799be2d1c571`, name `hh-gt10pc-linux-48dd0adcd6764e5e9b9452b1c7c1343b`, image digest as above, platform linux, `NetworkMode=none`, read-only root, user `65532:65532`. `log-driver=none` so `LogPath` is empty; container stdout was captured by attach in `linux/host/run-stdout.txt` (pip install of the pinned wheels, then `GT10PC_LINUX_NATIVE_COMPLETE`). Image inspect has `Os=linux`, `Architecture=amd64`, `RepoDigests=[]` (local image id, not a registry digest). The id matches the signed toolchain lock.

Guest proof that the work ran inside that container, copied out from the evidence mount: `linux/native/linux.json` (`system=Linux`, `python=3.12.14`, `target=Linux-headless`) and receipts whose `studio` path is `/output/consumer/<fixture>/install/releases/<manifest>/payload/studio`, `os_name=posix`. Godot/driver PIDs in those files (arena install godot pid 24, room reinstall godot pid 178, `ownership=process_group`) were written by the guest `run_process` and exported. The Windows host never recorded a non-zero container `State.Pid`.

## P3 — install on clean copies

**Requirement.** Install from the artifact onto clean copies of both fixtures on Windows and Linux headless; source and save unchanged; no global environment change; one roundtrip + Play readback; version/schema/hash match the runtime.

**Evidence (both fixtures, both platforms).** Clean baseline ledgers have no `addons/` entries. They contain the fixture art/scenes/scripts plus `owner-save.dat`.

- Windows: `windows/consumer/gt09-arena/project-before.json` (10 files) and `windows/consumer/gt09-room/project-before.json` (9 files). Live trees `windows/consumer/<fixture>/project/` were re-hashed and match `project-after-deactivate.json` exactly (arena 16 files, room 15). Save bytes on disk are `consumer-save-before-install\n` (sha256 `14bc01c77e9b74d7f45072684b127c452009c51aa94e5d4fe2102f00b0129c22`). Sprite hash matches the archive. Non-addon keys are identical across before, before-play, after-play, after-uninstall, and after-reinstall.
- Play after install: `windows/godot/gt09-arena/` and `windows/godot/gt09-room/` (`godot-host.json`, `godot-stdout.txt`, `godot-stderr.txt` empty, `parse-host.json`, `receipt.json`) and drivers `windows/drivers/<fixture>/`. Lifecycle stdout is `menu,start,pause,resume,restart,pause,resume,quit`, `lifecycle_complete=true`, seed 90127, freeze_errors 0. Word-boundary `error|warning|orphan` count is 0. Arena godot pid 42364 exit 0; room pid 14984 exit 0; host pid/exit match the receipt. Receipt: version `0.1.0`, `package_schema=hh-studio-package-0.1`, `os_name=nt`, `target=Windows`, `active_release` = Windows 0.1.0 manifest, `godot_sha256` = lock pin, `probe_sha256=0b1a7aa0…`, `launcher_sha256=ea522450…`.
- Journal: `windows/consumer/<fixture>/install/.install.json` command `install.<fixture>` action `install` status `COMMITTED`, active `85546002…`. Phases: `windows/consumer/<fixture>/native-phases.json` install active that manifest and `project_ledger` equal to before-play.
- Godot user data is under `windows/godot/<label>/godot-user/Roaming/Godot/.../logs/`, not a machine profile. No before/after snapshot of the host environment exists anywhere in c3e.
- Linux: `linux/native/consumer/<fixture>/project-before.json` (same file counts). Sprite and save hashes match the archive and the known save bytes. Install play: `linux/native/consumer/<fixture>/native/install/` (receipt, `godot-host.json`, stdout/stderr) and `.../drivers/install/`. Arena godot pid 24, room pid 112, exit 0, `ownership=process_group`, stderr empty, same lifecycle. Receipt version `0.1.0`, schema `hh-studio-package-0.1`, `os_name=posix`, `target=Linux-headless`, `godot_sha256` = Linux binary pin, active = Linux 0.1.0 manifest, studio path under `/output/...`. Journal in `install-state.json`: `install.<fixture>` COMMITTED active `e9683c33…`.

**HEAD checks.** Package re-verify: status string only (`_verify_rehearsal_matrix` / `_verify_final_matrix`). Deep path: `_verify_native_producer` and `verify_linux` as above, plus `verify_profile`. Neither function compares a host environment snapshot. `_verify_native_producer` does not re-walk the project tree (the live Windows tree does match the final ledger; that check is external to HEAD).

**Gaps.**

- BLOCKER (both platforms): package `--verify-only` never opens these files. Fix: from package verify, call `_verify_native_producer` and `verify_linux` and require the windows-producer host receipt. WIP `verify_raw_rows` does this; HEAD does not.
- MINOR (both platforms): “no global env” is not measured. Windows only shows a private `godot-user` tree. Linux relies on container `--env` and a tmpfs. HEAD never checks either. WIP does not add a check. Fix: record a host env hash before and after the producer (names plus a hash, no secret dump) and require Godot’s user dir to stay under the evidence `godot-user` tree.

## P4 — upgrade and rollback

**Requirement.** On copies that already have source and save: upgrade old→new and rollback new→old; migrate or explicitly reject an incompatible schema; rollback only to a trusted/compatible release; roundtrip + Play after each.

**Evidence.** Both fixtures, both platforms, after the install copy above.

- Windows plays: `windows/godot/gt09-arena-upgrade`, `gt09-arena-rollback`, `gt09-room-upgrade`, `gt09-room-rollback` plus matching `windows/drivers/`. Upgrade receipts version `0.1.1`, active `4c3c5e52…` (Windows 0.1.1 manifest), schema still `hh-studio-package-0.1`, same godot/probe/launcher hashes, lifecycle complete, exit 0, host pid matches (arena upgrade pid 15956, rollback 21472; room upgrade 19912, rollback 39248). Rollback receipts return to version `0.1.0` / active `85546002…`. `native-phases.json` lists install → upgrade → rollback with those actives, and each phase ledger equals before-play (source, save, manual note, addon bytes unchanged by Play). Journal: `upgrade.<fixture>` action `install` COMMITTED active `4c3c5e52…` previous `85546002…`; `rollback.<fixture>` action `rollback` COMMITTED active `85546002…` previous null. Profile catalog digest is identical across the three phases per fixture.
- Linux plays: `linux/native/consumer/<fixture>/native/{upgrade,rollback}/` and `drivers/{upgrade,rollback}/`. Upgrade version `0.1.1` active `ec98579a…`; rollback version `0.1.0` active `e9683c33…`. Arena upgrade godot pid 46, rollback 68; room upgrade 134, rollback 156. Same lifecycle, stderr empty, schema unchanged. `install-state.json` has the same command pattern (`upgrade` action `install`, `rollback` action `rollback`, previous ends null).

**Not in the package.** No migrated save (save bytes stay `consumer-save-before-install\n` on every ledger). No second schema. No receipt of a rejected incompatible package or of a rollback destination other than the previous manifest. `0.1.0` and `0.1.1` are the same schema series.

**HEAD checks.** Deep verifiers require upgrade active = 0.1.1 manifest and rollback active = 0.1.0 manifest, plus Play lifecycle on those two phases. They do not require a migration record or a rejected incompatible schema. Package re-verify checks neither.

**Gaps.**

- BLOCKER: same package-verifier hole as P3. WIP covers the re-verify wiring only.
- MAJOR (both platforms): TX12 / P4 “migrate or reject incompatible schema”, and “rollback only to a trusted/compatible release” as a refusal, are not in the artifacts. The evidenced path is a same-schema second install and a last-good rollback. HEAD `ConsumerInstall.rollback` refuses a destination that is not `state["previous"]` and re-reads that release, but c3e never shows that refusal. WIP does not add a case. Fix: on each platform, add a raw rejected incompatible schema (or a reviewed migration that changes and then reads back a schema id) that leaves source/save intact, and a refused rollback to a non-previous or untrusted id, with host exit/PID; require those files in `_verify_native_producer` and `verify_linux`.

## P5 — uninstall and reinstall

**Requirement.** Removing the addon keeps art/game/source/save. Reinstall works.

**Evidence.**

- Windows ledgers `windows/consumer/<fixture>/project-after-uninstall.json`: same non-addon keys and hashes as `project-before.json`, plus only `addons/hh_studio/owner-manual-note.txt`. Manual file still on disk is `owner edit must survive uninstall\r\n` (sha256 `7b6c675f33ae44eeecb31eddb1abd500026cf852b5a4417f6b7c95ace2b72530`), which is what HEAD expects. `project-after-reinstall.json` equals before-play (addon files back, manual kept, save and `project.godot` unchanged). Journal: `uninstall-addon.<fixture>` action `uninstall-addon` COMMITTED; `reinstall-addon.<fixture>` action `install-addon` COMMITTED active `85546002…`. There is **no** `windows/godot/<fixture>-reinstall/` Play.
- Linux: `linux/native/consumer/<fixture>/project-after-uninstall.json` same shape; manual hash is the LF byte string `3525ef617bdbf949152a91a77a3343b943b9c98a29bedcf82f19025cbefeb028`. `project-after-reinstall.json` equals before-play. Reinstall **does** Play: `linux/native/consumer/<fixture>/native/reinstall/` and `drivers/reinstall/` (arena godot pid 90, room pid 178, version 0.1.0, lifecycle complete, exit 0). Journal `uninstall.<fixture>` / `reinstall.<fixture>` COMMITTED. Linux project bytes themselves were not exported (left on container tmpfs); the proof is the ledger hashes, which match the archive and the known save/manual bytes.

**HEAD checks.** `_verify_native_producer` requires after-uninstall = baseline+manual and after-reinstall = installed ledger. It does not require a reinstall Play (phase list is only install/upgrade/rollback). `verify_linux` does require a reinstall Play. Package re-verify checks neither. Windows `.install.json` is not in the evidence hash set; Linux `install-state.json` is, and `verify_linux` recomputes `state_sha256` and matches command receipts.

**Gaps.**

- BLOCKER: package verifier, same as P3. WIP wires the existing deep checks, including Linux reinstall Play, and still does not require a Windows reinstall Play.
- MINOR (Windows only): reinstall is a ledger and a journal row, not a Play readback. Linux already plays. Fix: add a Windows `reinstall` native phase with host receipt, PID, and lifecycle stdout, and require that phase in `_verify_native_producer`.

## P6 — AUTH-07 profile

**Requirement.** Profile `hh-godot-gameplay-source-1` stays the same across install, upgrade, and rollback. Another project does not see it.

**Evidence.** Every Play receipt’s `profile.own.profiles[0].profile` is `hh-godot-gameplay-source-1`, version 1, `script_enabled` true, `authority` 0. Arena root `Node2D` / `project.registered.arena`; room root `Node3D` / `project.registered.room`. `profile.other.profiles` and `profile.default.profiles` are `[]`, and both have `fixture_enabled=false`. Catalog digest is stable across phases (Windows three phases; Linux four, including reinstall). Example Linux arena catalog `sha256:34a9762c9d77803e9cbc482d69a3c87dc9874cb767512e16e3c1c2f1ad495d57`; room `sha256:ce2c7f1203975dc12a58a74be00b6f799c06fd7a6e1ac83524db10806b93cc0c`.

The “other project” result is not a second project tree. `package/installed_probe.py` `profile_discovery` calls `profile_discovery(project_id="project.consumer.other")` and the default adapter in the same process, then stores `own` / `other` / `default` on the godot receipt.

**HEAD checks.** `verify_profile` (used by both deep verifiers) recomputes the profile digest, binds runtime file hashes to the manifest, requires that profile id, and requires `other` and `default` to be empty and disabled. Package re-verify does not call it.

**Gaps.**

- BLOCKER: package verifier, same as P3. WIP calls `verify_profile` indirectly via the deep verifiers.
- MINOR (both platforms): isolation is an in-process project-id argument recorded inside the Play receipt, not a second installed project. WIP does not change this. Fix: run discovery against a second clean project directory and keep that output in its own host receipt; require `other.profiles==[]` from that file in `verify_profile`.

## Hash re-derive vs producer PASS fields

| path | what it trusts |
| --- | --- |
| HEAD `verify_only` of c3e (`_verify_rehearsal_matrix`) | `matrix.json` `rows.P3`–`P6.status == REHEARSAL_PASS` only. Ignores `linux` and all raw files. |
| HEAD `_verify_final_matrix` | P3–P6 status strings (`target`, `producer`, `linux`). |
| HEAD `_verify_native_producer` (only if verify is pointed at `windows/`, whose matrix is `hh-gt10pc-matrix-2` DIAGNOSTIC) | Re-hashes evidence files. Compares ledger **contents** to archive members + known save/manual bytes. Reads Godot stdout for lifecycle. Does not re-walk `project/`. Does not read `.install.json`. |
| HEAD `verify_linux` (only with `--target Linux-headless` and explicit artifacts, or from `run_rehearsal` at production) | Re-hashes `producer.json` evidence and `native/linux.json` evidence. Parses docker inspect stdout. Compares ledgers to archive-derived hashes. Requires container `State.Pid==0` after exit. |
| `children/windows-producer-receipt.json` | Real host exit 0 and pid 13296. HEAD package verify does not open it. WIP does. |
| `linux/producer.json` `status=DIAGNOSTIC_PASS` | Written by `run_linux` after the container exits. `verify_linux` requires that field **and** re-reads host receipts and native files. Package verify never gets there on HEAD. |

`children/windows-producer-stdout.txt` is the probe print. The deep Windows verifier print is task `stdout.txt` line 0, produced by the matrix process after the child returned, not by a field inside `matrix.json`.
