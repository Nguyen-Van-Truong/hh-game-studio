# GT-05 S64 requirement-to-evidence map

AUTHORITY=0. Coordinator coverage, not a critic verdict. The manifest binds
exact bytes; PASS fields alone are insufficient. Scope: fixed original fixture,
Windows staged immutable assets; public_ack=false, editor_activation=false.
This supersedes the pre-nav `requirements.md`, retained as historical handoff.

## Selected evidence

Paths below are under `studio/.local/reviews/`.

| Lane | Run ID | Result |
| --- | --- | --- |
| Full unit | gt05-units-s64-02 |233 run,232 pass,1 symlink-permission skip; actual target/wrapper0, tree verified |
| Native storage | gt05-snapshot-native-s64-02 |11 cases including7 death86 cuts, correct recovery and last-good preserved |
| STAGED | gt05-staged-cut-s64-02 |Death86 after witnessed STAGED; full prefix reread, selector absent, UNKNOWN, no changed bytes |
| Actual publication | gt05-publication-s64-02 |Full chain,4 real payloads, protected readback, exact same/cross-owner retry and readonly reopen |
| Bone migration rejection | gt05-bone-migration-s64-02 |Actual Blender rename/delete, save/reopen; installed admission rejects before export/publish |
| Coordinator visual | gt05-visual-review-s64-01 |9 image hashes equal previously inspected bytes; front/walk22 opened again; not independent review |

The selected asset chain uses `gt05-` plus producer-repeat-01, producer-s62-01,
producer-edited-01; validation-s62-01, validation-s62-02,
validation-edited-s62-02; consumer-s64-02, visual-s64-01, reimport-s64-01,
rejections-s64-01. Full test/publication source has143 files. The strict asset
chain reads47 source files plus723 local artifacts, checking complete per-stage
maps against current bytes. No old capture is relabeled as a new execution.

## Requirement → verification → evidence

| Requirement | Code and tests | Actual result / limit |
| --- | --- | --- |
| TQ00 dependencies, source, real exits | Acceptance receipts; verify_run.py; package verify.py/test_verify.py | GT01–04 accepted. Full143 map bound across captures; host PID/exit/tree, markers, snapshots, artifact hashes and Git blobs checked. Two new signatures required. |
| 2.4/TQ05 units/axis/bounds/rig/skin | Locked asset-profile; native producer/GLB/Godot comparison; contract tests |1m cube/axes,12 meshes/12 bones/4 skins/2160 skin vertices/792 poses. Bounds1mm, scale1e-4, angle0.1degree, clip1sample/30Hz; IDs/license exact. |
| Clips, root motion and LOD | make_actions, skeleton/skin/track samples, LOD tests |One avatar+outfit/shared rig, idle/walk in-place30Hz;36tracks/31keys each. Body576/144triangles,outfit288/72; scene1200. Native LOD visibility. Unsupported unbaked features not silently converted. |
| Navigation paths/collision §2.4 | authored.gd top triangles; probe map sync/query; consumer checks;8 nav regressions |Map0→1(no owners)→2(exact owner);4vertices/2polygons/24m². Two actual3-point diagonal paths5.83095169m, correct endpoints/region/y=0/UP normals. Real collider ray hit. Counts alone do not pass. |
| PBR/texture/color/visual | Material/channel/pixel readbacks, PNG decoder, visual tamper tests |3 embedded textures; actual PBR/culling/normal/ORM checks;6views+31frames/clip=68 PNG,640square,9draw calls. Original checker visible; override restored. Minimal fixture art, not game quality or performance benchmark. |
| Manifest/source/license | snapshot_provider/state metadata/catalog guards |4 actual payloads; creator/license/attribution/time, toolchain/exporter/preset/validator/binary/tolerance/semantic/artifact hashes and9 evidence roles. Embedded textures, no external inputs or published cache. |
| Naming and migration GT05/TX07 | Naming convention/lint, exact names; consumer negatives; run_bone_migration.py |Native bn_head→bn_head_migrated or→null, save/reopen, installed admit_observation rejects OBSERVED_NAME_SET. Actual GLB joints/weights/clips/catalog/socket ancestry derive affected consumers; explicit proposed mapping, accepted_mapping=false. No auto-migration/import claim. |
| TX04 unsupported/external/missing | Closed producer, disable-autoexec/use_scripts=false, allowlists/caps and malformed input tests; unchanged GT04 boundary |Only hash-pinned trusted .blend opened. Missing texture/unsupported fields reject. No arbitrary artist intake, external dereference or generic bake/UI feature. |
| TX07 semantic negatives | preflight/consumer tests; check_native_observation_rejections.py |27 copied native-observation mutations reject exact error/site across axis/scale/skin/clip/material/texture/socket/LOD/proxies. Supplement native positive/nav/migration, not27 malformed Blender imports. |
| TX08 repeats/edit/reimport/cache | verify_repeat, strict chain repeat/edit; same project/cache reimport |Two baseline GLBs byte-identical; actual crate0.6→0.8m changes geometry/collider/signature, preserves unrelated data. Reimport preserves authored script/socket/material. Frozen original inputs and generated preset have distinct hashes. Broader cache/platform matrix staysGT08. |
| TX09 publication/replay | snapshot_owner/state/provider + protected files/custody/events/journal tests |4 actual payloads/readback, exact same-ID replay without provider rerun, cross-owner journal routing, readonly reopen. Source save is not active game/editor release. |
| TX09 each persistent phase/crash/Stop | Native11-case matrix plus pinned STAGED supplement; prefix/readback unit faults |Actual death at INTENT, first artifact, manifest, STAGED, SELECTING, selector, before witness, terminal. Preterminal UNKNOWN; unwitnessed suffix HELD; witnessed terminal COMMITTED. Stop before provider executes none; after selector staysUNKNOWN; previous complete root preserved. |
| TX09 I/O/filesystem limits | Accepted protected local primitives; injected I/O/readback tests |Fresh files in owned same-volume root; no external destination/cross-volume move admitted. Injected OSError is not actual antivirus, disk exhaustion or power-loss proof. Active replace/scheduling staysGT07. |
| Log admission | verify_run.host + resealed error/success tests |Error: followed by space rejected; benign counters accepted. Exact4root-skin+1shared-ORM Blender warnings explained and body/count checked; no unexplained warning/error/stderr. |
| Stop/deadline/lease/source/caps | AbsoluteDeadline/phase_guard, original deadline outside mutex, guard before writes, owner/provider tests |Verification60s in owned90s worker; engines20s Job cap.1MiB perblob/caps unchanged. Ambiguity UNKNOWN; Stop checked across reads/phases, outer process bound covers individual native calls. |

## Reuse and boundaries

GT04 accepted source38f6b9a; source closure
f5ae5dfbb451d3204197c2b21486c586698089ac24d14d23641a9182b5e42673;
review8ea276e98f3137a5f3623fce00d0760ae0c1fe6d17a77a330e98fa8839a31950.
GT02/03/04 acceptance receipts are in review_files. Reused protected storage,
custody/events/journal/deadline bytes remain unchanged; old signatures do not
sign new pipeline code.

Explicit skip: test_producer_contract.ProducerContractTests.test_symlink_staging_rejected_where_supported;
host lacks native symlink creation permission. Simulated path tests do not
claim this skipped capability was exercised.

GT06 input/perf, GT07 activation/recovery scheduling, GT08 Windows/Linux/physical
Android, GT09 conformance and GT10 package remain separate gates. HH World follows
GT10. No HUMAN/RELEASE acceptance implied. Failed attempts/pre-nav notes retain
original bytes locally; only manifest-selected runs form this candidate.
