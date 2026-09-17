# GT04 S60 — independent critic B2

Date: 2026-09-17, Asia/Saigon.

**VERDICT=PASS**  
**TICK=yes**  
**Scope: the declared bounded Windows Blender adapter and protected immutable fixture publication component in GT-04.**

No acceptance-blocking defect was found in this focused independent review. This is a fresh verdict for the hashes below, not a transferred S59 signature. It is one critic's approval; the coordinator must still obtain the other independent verdict on the same closure and perform the plan transition. This report does not tick a plan or accept GT-05.

## Frozen identity and independence

- Git HEAD: `38f6b9abd261cfc0f85f5f119a1eeeba84e35c74`.
- Review closure: `8ea276e98f3137a5f3623fce00d0760ae0c1fe6d17a77a330e98fa8839a31950`.
- Source closure: `f5ae5dfbb451d3204197c2b21486c586698089ac24d14d23641a9182b5e42673`.
- Execution closure: `407fff4e453fb1702a32fbc8ae1ee5eff7c3dcb0b99338a504ae39dc69d67824`.
- Native runtime digest: `27846f581ba8ac356a8f4abe7f4010789cc47241dcb52c7707e24ef7c85f6040`.
- Blender executable SHA256: `8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06`.

I read the scoped AGENTS, current tools-plan GT-04, referenced section 2 contracts, TQ00/TQ01/TQ04 and TX02–TX06, the candidate README/coverage, implementation contracts, relevant runtime/test code and original evidence. I did not read another critic's report. No subagent, native engine, journal owner or mutable recovery session was launched. Python ran with `-B`; Git byte reads used `core.longpaths=true`. No tracked source change was present. Existing unrelated untracked history was not used as S60 acceptance evidence or modified.

Only this report was written. File-only verifier functions and their negative tests ran with `Path.write_bytes`/`write_text` blocked and directory creation restricted to already existing directories. Their report-writing mains were not run.

## Independent checks and results

| Check | Result |
|---|---|
| `checkpoint.py check`, including a final repeat | Exact review closure; 909 bound Git files and 1,385 retained raw files all match |
| Independent `git cat-file --batch` verification against HEAD and index | 910/910 byte hashes match in each domain; `files.json` adds `review-closure.json` to the 909 bound files |
| `binding.verify()` | All 143 execution files, 140 source files, 58 runtime files and actual pinned executable match |
| `verify_views.py --local-raw` | All seven packages match exact raw inventory and deterministic transformations |
| `verify_evidence.verify()` for scene/checkpoint/export | PASS for each; 3,723 assertions per profile |
| `verify_matrix.verify()` | PASS; 17 lanes, 240 top-level native checks, 16,061 verifier assertions |
| Independent unittest loading of rejection modules | 10/10 evidence tests and 6/6 matrix tests pass, with writes blocked |
| Existing clean Git reconstruction, independently rerun view verifier | Portable verification passes; missing-original verification raises `FileNotFoundError` as required |

The current Git inventory digest is `4085d9f35d36b7e315f9bf0993692f5844edda2efe76ec7cb50c1aaf2b65e024`. The older clean-reconstruction report describes its own 909-file input inventory; it is not mislabeled as reconstruction of today's 910-file inventory or of original native raw bytes. Current HEAD/index bytes were checked separately above.

Primary package references are [README](20260917-gt04-s60-audit/README.md), [coverage](20260917-gt04-s60-audit/coverage.json), [review closure](20260917-gt04-s60-audit/review-closure.json), [source closure](20260917-gt04-s60-audit/source-closure.json), [execution closure](20260917-gt04-s60-audit/execution-closure.json), [profile verifier](20260917-gt04-s60-audit/verify_evidence.py), and [matrix verifier](20260917-gt04-s60-audit/verify_matrix.py).

## Requirement and evidence assessment

**Native/UI ownership, postconditions and TQ04/TX02.** The UI lane contains six real GUI/background phases, with native result markers, actual process exits, Object/Edit mode operations, context/selection restoration, duplicate create/undo behavior, native undo/redo and reopened blend readback. I inspected the frozen evaluator and adapter paths rather than accepting a check count alone. The material lane adds native opaque Principled creation/update, history, fresh checkpoint reopen, and geometry/material binding against the exported GLB. The IPC hello binds native PID, main-thread execution and one Python thread. Network/host work lives outside Blender; the owned main-thread queue dispatches bounded operations.

Evidence: `studio/.local/reviews/20260917-gt04-s60-matrix/ui/{capture.json,native.json,native-host.json}` and its GUI/background result/log files; `material/native.json`; `ipc/native.json`. Portable counterparts are under `20260917-gt04-s60-audit/portable/matrix/view/`. The matrix verifier checks every captured artifact hash and recursively launched runtime binding.

**Admission and TX03/TX04.** `export_profile.preflight` rejects any library/image datablocks before reading their filepath, resolving Blender paths or probing storage. `UIAdapter` checks revision/context before exporter preflight. The five S60 unit regressions cover unreadable reference properties, absolute/UNC/device/relative forms, packed/generated images and stale revision/context without operator calls. Native IPC and material admission probes independently block both `Path` and `bpy.path.abspath` while rejecting missing texture, existing linked library and missing library. Native driver, Geometry Nodes, addon and unsupported material probes also reject, preserving the bounded fixture. The test libraries themselves are trusted tiny local fixtures, not hostile external-host intake.

Evidence: `studio/blender-addon/{export_profile.py,ui_adapter.py,SUPPORTED_PROFILE.md}`, `studio/tests/blender/{test_export_admission.py,export_negative_probe.py}`, `studio/.local/reviews/20260917-gt04-s60-matrix/ipc/admission.json`, `material/native.json`, and [native no-I/O summary](20260917-gt04-s60-audit/native-no-external-io.json). Images, external libraries, rigs, clips and arbitrary artist files are not advertised as supported. TQ04's materialized-input rule grants no exception to this unsupported-input boundary.

**Real HTTP profile behavior and publication.** Each independently audited scene/checkpoint/export profile records 36 actual HTTP calls, 49 client checks and 10 native checks. Scene's frozen complete unit run is 599/599; checkpoint/export have 328/328 focused runs. These are verified recorded executions, not newly claimed native runs by this critic. The audit binds canonical request/response hashes, grants/discovery, advisory previews, the private command translation, persisted terminal bytes, exact lookup/retry, revision progression and actual before/after differences. Reader/foreign-session, conflict, deadline, route and capacity denials do not fabricate observations.

The selected `checkpoint.blend`, `scene.glb`, manifest and selector bytes are read and hash-bound to protected file versions, terminal response and native background reopen/export. GLB geometry/materials are checked against the observed scene. The UI, export and separate client PIDs/exits match their host records; successful Jobs close with observed active count zero and no retained handle/taint. Each profile's unit/native outer targets and wrappers exit zero with verified trees.

Evidence: `studio/.local/reviews/20260917-gt04-s60-{scene,checkpoint,export}-01/` contains `capture.json`, unit/native host and logs, `client.json`, `client-exit.json`, `writer-native.json`, `publication.json`, native owner launch/exit/close files and selected protected artifacts. [Publication contract](../../studio/blender-addon/PUBLICATION.md) and [writer contract](../../studio/host/blender/CLIENT_WRITER.md) correctly constrain all three profiles to create-only immutable bundles and preserve `public_ack=false` and `scene_state_durable=false`.

**TX05/TX06, cleanup and recovery.** The IPC fault lane proves an actual over-limit allocation with expected `MemoryError`/exit 17, deadline termination and active-export Stop; these intentional failures remain failed exports with no output GLB. They are not promoted to successful jobs. The cleanup lane retains the original failed report and the exact owner across two close failures, then verifies final cleanup without rewriting the original outcome. Lease/FIFO lanes exercise two distinct client processes, increasing fences, expiry, late authenticated rejection, bounded waiters and Stop cancellation. Native callbacks recheck authority before effect; protected publication rechecks authority, readback and barriers before its witnessed terminal.

The five crash cases independently record host exit 86 and exact owned children changing from live wait 258 to dead wait 0. Recovery yields UNKNOWN after intent, before selector and after selector; HELD before terminal witness; COMMITTED only after terminal witness. The four Stop cases yield UNKNOWN at export/before selector/after selector and COMMITTED after terminal. Observed native Stop times are approximately 16–31 ms for these cases, not a general performance guarantee. Persisted recovery graphs remain unchanged. The checkpoint consumer reopens a clean predecessor into a new native PID/generation, reads exact mesh/transform/material/context, and rejects mutation/lease requests at both host and native boundaries.

Evidence: matrix `ipc/{deadline.json,oom.json,stop.json}`, `cleanup/native.json`, `durable/native.json`, `fifo/native.json`, `checkpoint/native.json`, `deadline/absolute-deadline-native.json`, and every crash/Stop lane's `capture.json`, `observed.json`, `ready.json`, `recovery.json` and terminal replay where applicable. This establishes baseline fail-closed historical recovery. It does not establish writable restart, restored Undo, arbitrary recovery after a crashed predecessor, physical power-loss durability or GT-07 cross-app recovery. Protected storage/barrier primitives are reused from accepted GT-02; this review does not claim a new physical disk-full experiment.

## False-PASS and portability assessment

The rerun negative suites reject stale/missing source, boolean fabricated exit zero, missing runtime file, retained Job, wrong exit PID, changed publication profile, forged artifact/preview hashes, missing matrix checks and forged committed recovery from an unwitnessed/unknown prefix. The empty-client-stderr regression confirms that even an empty required log remains in the captured inventory. The bound evidence-view suite records 12/12 tests covering tampering, omitted logs/binaries, metadata scope, unregistered paths and traversal; I inspected that implementation and its recorded output rather than rewriting its test report.

The committed view is explicitly transformed explanatory evidence. It retains separate original/view hashes and byte sizes; native binary/source/cache entries are hash-only. Original receipt/journal hashes are never recomputed from sanitized text as though it were raw. Local verification checks every original and exact transformation. On the existing clean reconstructed tree, portable integrity succeeds with `local_raw_verified=false`, and requesting original verification correctly fails. I also read its captured zero target exits and empty stderr. Scanning bound JSON/text/Markdown/snapshot files found no current workstation root or username. This is the current fixture's path-privacy boundary, not a general secret-detection certification.

TQ01 is adequate for this scoped gate: source/lock and portable evidence are reproducible from Git, original native bytes were available and independently checked here, and the inability of a clean checkout to recover those old local originals is explicit. Retain the exact 1,385 local raw files for future original-byte audit. A fresh native reproduction will have new process identities, timestamps and potentially binary bytes and therefore needs a new evidence closure. A portable-only reviewer cannot reuse this verdict to assert possession or verification of the old raw set.

The PASS remains limited to the declared bounded component: box meshes, typed transforms, closed opaque materials, guarded session history, fixed-slot saves and protected immutable publication. It grants no arbitrary artist-file intake, external textures/libraries, writable restart, restored Undo, complete Blender-to-Godot asset pipeline, Android, deployment or HH World acceptance. Any source/evidence change requires a new matching review binding.
