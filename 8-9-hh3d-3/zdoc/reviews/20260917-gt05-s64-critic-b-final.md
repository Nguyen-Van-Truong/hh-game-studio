# GT-05 S64 independent final critic B

VERDICT=PASS
TICK=yes

Reviewed 2026-09-17, Asia/Saigon, completed after 19:51 +07:00.
Reviewer: independent critic B, task `gt05_critic_b_final_s64`.
AUTHORITY=0. This is a critic recommendation to the coordinator; it does not tick the plan or grant human/release acceptance.

The frozen GT-05 candidate satisfies the specified gate for the original Windows fixture, Blender-to-GLB-to-Godot verification and protected immutable **staged snapshot** publication. I found no blocking defect in that scope. This verdict is bound to the exact commit and four digests below, not to later source changes or a broader product claim.

| Binding | Exact value |
| --- | --- |
| Git commit | `808d8ba94e3c39b19c8381072775590b7cafdc0c` |
| Manifest SHA256 | `fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b` |
| Source closure, 143 files | `c141d54b80022ca7fefdf81f83e7e1078d3cc6aa43954831f82bb3178338a135` |
| Review closure, 13 files | `21061e5e6c8cae1ab7bcb724f2c21dace72c6d1198d0ecab70b7c32e9a4c12e1` |
| Raw closure, 1,722 files | `1cd71ca1c2ae173f7bc4701e25f44ed35e0750a426bafd7afc8bc560be99feb5` |

The package is `20260917-gt05-s63-audit/manifest.json`; the retained development folder name does not change its selected S64 run IDs or `requirements-s64.md`. Closure digests use sorted UTF-8 `path + NUL + per-file SHA256 + LF`. The manifest digest hashes its exact bytes. Provider JCS and strict-chain compact-JSON source hashes have distinct domains; I compared their per-file maps instead of asserting these digests should be equal.

## Independence and verification performed

I read the nested `8-9-hh3d-3/AGENTS.md`, current tools-plan header and GT-05, sections 2.3/2.4, TQ00/TQ05 and TX04/07/08/09. I read the selected requirements and dependency acceptance receipts, not another critic's report. I did not launch Blender/Godot, publish, reopen custody stores, modify source/governance, stage/commit, or spawn agents. My sole persistent write is this report.

Initial and final HEAD checks matched the commit above; tracked source was clean. The initial process inventory had no Blender/Godot process. Untracked historical evidence exists outside the frozen candidate and is not included as acceptance evidence.

- `python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt05-s63-audit/verify.py --git-ref HEAD`: actual exit 0; 157 Git blobs verified, comprising source, review and manifest.
- `python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt05-s63-audit/test_verify.py`: actual exit 0, 18 tests passed. The retained S63 in-memory fault fixtures are explicitly historical; the five bone supplement tests exercise retained native rename/delete evidence. I did not mislabel this as rerunning the full native suite.
- Independent inline Python recomputed all three inventory digests, read every raw file, and fetched each of the 156 source/review blobs directly with `git cat-file blob HEAD:<path>`. I separately compared the manifest Git blob to its disk bytes. All matched.
- Independent comparison of all 13 component stage maps verified their captured source snapshots and current non-local runtime bytes. Five final execution lanes carry the same full 143-file map: units, native storage, publication, STAGED supplement and bone supplement. Mutable baseline project inputs were correctly checked against their original source snapshots; reimport intentionally changes those project inputs.
- I recomputed `studio.pipeline.verify_run.verify_chain(..., require_current_source=True)` with a 60-second read-only deadline. Captured completion was exit 0 in 20.672 seconds; its proof exactly equaled `verified-chain.json`: 47 source files, 723 local artifacts, all nine evidence roles and four payloads. No engine was launched by this call.
- I compared 84 inherited `host/core`, `host/blender`, `protocol` and `blender-addon` source blobs against accepted GT-04 checkpoint `38f6b9a`; all remained byte-identical. GT-02/03/04 receipts are ACCEPTED; their signatures are not treated as signatures on new pipeline code.

## Findings against the gate

**Source, pins and admission.** The profile/naming contract, toolchain/exporter/import preset and validator dependencies are bound. The GLB container checks exact chunk/layout bounds, closed fields and extension/URI policy before native intake. Accessor decoding and semantic checks, bounded PNG inflation with CRC/dimensions/aggregate decoded caps, and native process resource ownership form separate layers. The producer uses original fixed inputs, explicit save/reopen observations, disabled autoexec and pinned exporter settings. Unsupported general artist input is outside this profile. No shared protected-store limit was increased to fit the fixture.

**Actual asset chain and semantics.** Two baseline exports share GLB SHA256 `e85e536137208ba84adbc875b6fb647b5a4e49156344e03e2e8947a7ae91e377`. The deliberate crate width change from 0.6 m to 0.8 m changes geometry, collider bounds and semantics while preserving unrelated observed data. Python admission and pinned Khronos results are bound to captured processes and payloads. The native Godot comparison reports 12 meshes, 12 bones, 792 pose-bone samples, 2,160 skin vertices and two clips. Direct parsing of the GLB JSON confirms **one distinct glTF skin referenced by four skinned mesh nodes**, not four distinct rigs/skins. The `requirements-s64.md` shorthand “4 skins” must be read as those four mesh consumers; this report makes the exact count explicit.

**Godot navigation, collisions and reimport.** I inspected `authored.gd`, `probe.gd`, the Python comparator and actual baseline readback. Navigation is built from the imported proxy's two top triangles, four vertices and 24 m² surface. Baseline PID 12576 records map iteration 0, then iteration 1 with zero endpoint owners, then iteration 2 with all endpoints owned by the expected region. Both actual `NavigationServer3D.map_get_path` queries return three points, length 5.83095169067383 m, correct endpoints within tolerance, points on y=0 and UP normals. Enabled/count flags alone cannot satisfy the comparator. Eight navigation regressions appear as passed in the frozen unit log. The live imported collision ray and LOD/socket/rig/material comparisons are also recomputed by the strict verifier. Baseline/import/visual/reimport process records have matching PIDs, exit 0, natural tree exit and zero active owned processes. Reimport uses the same project/cache, changed GLB and preserved authored script, socket and material override; the before/after preset byte hashes are intentionally distinct.

**Visual evidence.** I independently opened the six native Godot views plus `idle_00.png`, `walk_08.png` and `walk_22.png`, all under the manifest-bound consumer output. They show the original block avatar, teal outfit, axis/cube fixture and red/blue checker prop, with opposite walk arm poses. The strict verifier checks all 68 PNGs and native capture bindings, original PBR visible during capture, and restoration of the authored override. Side views naturally occlude parts of the scene; the images do not prove every surface independently. Nine draw calls per capture are fixture observations, not a performance benchmark.

**Bone migration rejection.** I read the supplement driver and actual before/after observations, changed `.blend` hashes, process logs and reports. This is a real Blender mutation: rename `bn_head` to `bn_head_migrated`, or delete it in Edit mode; save a changed file, reopen, observe, then invoke the installed `admit_observation`. Native PIDs 41832 and 32956 exit 0 and emit report/hash-bound `OBSERVED_NAME_SET` rejection markers. A setup exception would not satisfy that check. The affected-consumer graph derives the shared skin, four mesh consumers and idle/walk channels from actual GLB indices/weights. Body LODs have direct head weights; outfit meshes share the rig without direct head weights; `socket_hand_r` is outside the changed bone ancestry. Both reports supply an old-to-new/null proposal with `accepted_mapping=false`, preserve the last good publication and perform no export/publication. This proves safe rejection and migration reporting, not an implemented automatic migration or successful import of changed bones.

**Crash, Stop, replay and publication.** I inspected `snapshot_owner.py`, `snapshot_provider.py`, state/readback verification and both native fault drivers. Validation occurs before INTENT; protected blobs/files are reread; STAGED, SELECTING, selector and witnessed TERMINAL precede a committed receipt. Read-only reopen checks the selected bundle or incomplete prefix. Exact retry resolves before provider execution, and a second owner routes through the durable journal to the original custody-bound snapshot.

The native storage matrix contains 11 cases with host-captured wrapper/target exits and seven real child exits 86. INTENT/artifact/manifest/SELECTING/selector cuts recover UNKNOWN; a terminal event without its custody witness is HELD; a witnessed TERMINAL recovers COMMITTED. Stop-before-provider executes no provider; Stop after selector and injected write failure do not return committed. The separate STAGED child also exits 86 after the durable phase, reopens UNKNOWN, rereads the full prefix, has no selector and preserves the completed last-good graph. These outcomes are bound to raw observations, readiness markers, source snapshots and unchanged bytes, not just success booleans.

Actual publication independently proves four real payloads, protected readback, exact same-owner retry, read-only reopen and cross-owner retry without another provider run. The payload hashes recomputed by this review are:

| Payload | SHA256 |
| --- | --- |
| `fixture.blend` | `ad88ee8d6c15d85acc7332d6896818f82309869a57c9cf4667ea91019a245956` |
| `fixture.glb` | `e85e536137208ba84adbc875b6fb647b5a4e49156344e03e2e8947a7ae91e377` |
| `producer-report.json` | `13a0416950aa2f6e4589442e1fa917c023bfe8395af717f803d1a1362fce8eee` |
| `asset-manifest.json` | `1dfb3a3897c7471a0f1be22fde78d1bdc751823a5f6b9268c38d3e28c166665a` |

The receipt SHA is `261d4ba19c7ba985d1201c9aea9f1668c4a5c73d801f50954d77318426e58403`; strict proof SHA is `4239fd7586d0106b6d363e4534e77163829f0c555ca74a1f6035dfab313769e7`. `public_ack=false` and `editor_activation=false` remain essential scope boundaries.

**Logs and tests.** Frozen full-suite stdout, stderr, roster, source map and host record agree on 233 run = 232 pass + one explicit Windows symlink-creation-permission skip, with no failure/error. Native logs admit only the exactly counted, explained exporter warnings: four root-skin warnings and one shared-ORM sampler warning. The current nonproducer log regex detects `Error:` followed by whitespace; the regression reseals captures and checks the actual `CAPTURE_LOG` rejection site, while benign zero counters remain accepted. I did not infer that the prior gap was fixed from a summary alone.

## Selected runs and limitations

The six manifest-selected run IDs are:

- `gt05-units-s64-02`
- `gt05-snapshot-native-s64-02`
- `gt05-publication-s64-02`
- `gt05-visual-review-s64-01`
- `gt05-staged-cut-s64-02`
- `gt05-bone-migration-s64-02`

The 27 negative cases mutate copied native observations and hit specific rejection sites; they are not 27 separate malformed Blender import executions. The native storage death matrix and STAGED supplement use synthetic payloads; actual asset admission/publication is established separately. Injected `OSError` is not proof of real antivirus contention, disk exhaustion or hardware power-loss durability. Fresh immutable files remain within owned same-volume protected roots; caller-controlled cross-volume move and active replacement are not supported here. The skipped symlink test remains unexecuted on this host.

Raw evidence is retained locally and hash-inventoried; Git alone does not transport all native binaries/assets/images. This review verified recorded native executions and recomputed their checks without rerunning engines or custody recovery. Component evidence reuse is justified only by exact unchanged per-component bytes.

GT-06 input/observe, GT-07 cross-app activation and broader scheduling/recovery, GT-08 platform/physical-Android matrix, GT-09 conformance, GT-10 installation/package and HH World remain separate gates. No human, benchmark, gameplay, arbitrary artist intake or active release acceptance is granted. Current tools-plan header/`CURRENT_VALID_WP=GT-05` governs routing; isolated historical preparation/status prose does not reopen an accepted dependency. The coordinator may use this PASS/TICK=yes only with a second independent verdict on this same frozen candidate.
