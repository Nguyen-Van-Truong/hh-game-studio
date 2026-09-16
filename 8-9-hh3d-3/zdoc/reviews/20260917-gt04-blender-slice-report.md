# GT04 first Blender fixture slice — implementation capture

AUTHORITY=0. ACCEPTANCE=false. PUBLIC_ACK=false. No plan checkbox or commit is
authorized by this report. This bounded lane runs in parallel with GT03 under
plan §8.1, following accepted GT02. Baseline when the native capture began was
`c4fac2e6d8643da4c57c9049168bdd45460282b8`.

The new private adapter implements strict typed inspection, fixed box-mesh
creation, and typed transforms with main-thread admission, stable IDs, scene
revision/context preconditions, bounded process-local command dedupe, conflict
rejection, Stop admission, and native readback. Its trusted fixture leaves and
restores Edit Mesh mode with object selection/active ID preserved. Fresh owned
checkpoint and final files are saved; independent Blender processes reopen
both. No arbitrary script/path operation or user artist file is admitted.

## Actual capture

`20260917-gt04-blender-02/result.json` reports a successful bounded fixture run:

| Process | Actual target PID | Actual target/wrapper exits | Native checks |
| --- | ---: | --- | ---: |
| Python unittest | 13616 | 0 / 0 | 18 tests, no skips |
| Blender edit/save | 36500 | 0 / 0 | 27 |
| Blender final-file reopen | 22416 | 0 / 0 | 9 |
| Blender checkpoint reopen | 41700 | 0 / 0 | 7 |

All four captured Job-tree observations are zero/`tree_verified=true`; no
timeout occurred. Native stderr files are empty and all exact ordered
`GT04_CHECK`/`GT04_RESULT` records agree with the corresponding JSON files.
The inherited GT01 helper does not check the native `CloseHandle` return, so
this report does not elevate its tree observation into checked handle-closure
proof. No Blender process remained in the post-run process listing. The engine
resource was then released to the semantic parity worker.

Capture UTC: `2026-09-16T18:55:42.330477+00:00` through
`2026-09-16T18:55:46.788308+00:00` (2026-09-17 local Asia/Saigon).
The host uses 30 seconds for Python tests and 60 seconds for each Blender
process, via the unchanged gated `build/bootstrap/run_fixture.py`.

The executable was read from
`studio/.local/tooling/blender-5.2.1-windows-x64/blender.exe`, with SHA256
`8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06`
before and after. Native API version tuple is `(5,2,1)` and display string is
`5.2.1 LTS`.

Frozen source closure (nine files, including unchanged runner and toolchain
lock): `6190abcf73ab5c01e2e5799ed5210179b771a4165f76a430a3275948c729b847`.
Current source, frozen snapshot, and executable were unchanged after the run.
The result JSON SHA256 is
`9c6fbd1d7e0f09157b4e8b21c99bdaa93cc6325390e72b46010ac898318154e4`.

| New source | SHA256 |
| --- | --- |
| `studio/blender-addon/adapter.py` | `e6fdbd9d292b8b7aa0a9ba455a89e8336d8e2b354c82adaac3dfe39fc5080358` |
| `studio/blender-addon/contract.py` | `034b86182742e444a74b645761f34641b4cd576b0fb4a43e43e4e6c0a7e54e25` |
| `studio/blender-addon/README.md` | `bcf2ea1af7afc951f6f4995e11ebc398b325801c5a23935d8ae4cb11364f520c` |
| `studio/tests/blender/blender_probe.py` | `74eac1188b8507201a046dab6b8eb5ebb9d5a4d6033493ec1aa45cdc18451778` |
| `studio/tests/blender/run_blender_probe.py` | `9f11be8a3ad3c2dee621e5449de001d537083d859d7f276fef04347aab0b1cfa` |
| `studio/tests/blender/test_contract.py` | `4929d9e5128eb176f47ff1740d25f33d0f76a3e11898074a7bcbaf8f3ebfe531` |
| `studio/tests/blender/test_probe_evidence.py` | `545ded79f7f3e840b65ce412625f0ef1a4bbba8bc9b9bc8c88b9b45bd92b5574` |

The final original fixture is 86,917 bytes with SHA256
`66db2eb2b068ab04ee3ba5549b8a1f60d869e36975f8733bcf4ed394267b0fe5`.
The empty original checkpoint is 85,671 bytes with SHA256
`c6492012f9b793523c06426f208e195cd8e12d8ce19c3c4f23689c7485fbfe4b`.
These are generated fixture artifacts, not imported reference assets. The
package also retains an incidental isolated Blender extensions compatibility
cache; it is not source or authority and should not be represented as shipped
product data.

## Preserved failed attempt

`20260917-gt04-blender-01` is not a passing package. Its edit process returned
actual exit 0 after 27 successful native checks, but the host verifier rejected
the native display version `5.2.1 LTS` because it initially expected `5.2.1`.
No reopen/checkpoint process was launched for that package. The raw logs,
partial result and old frozen source remain unchanged. Only the host exact
version expectation and its synthetic evidence test fixture changed before a
new complete `-02` run; the original adapter/probe code did not change.

## Scope and remaining work

This is a first functional vertical slice, not completion of TQ04 or
TX02/03/04/05/06. It demonstrates main-thread rejection before `bpy` access,
typed finite/bounded fields, stale/manual-change rejection, mode drift,
duplicate/conflicting retries, stable ID collision rejection, embedded text
profile rejection, context restoration, Stop admission, fresh checkpoint,
save/reopen mesh/transform equality, and absence of a public ACK.

Still unimplemented/unproven: UI extension and nonblocking IPC; durable dedupe
and lease/fencing/FIFO; semantic undo/atomic rollback; edit-element selection
history; protected GT02 filesystem ownership and transactional publication;
export/material operations; full external resource allowlist/materialization;
hostile `.blend` parser isolation; CPU/memory/disk quotas; interruption,
timeout/OOM/crash recovery and concurrent artist editing. Unknown native
exceptions after mutation hold the adapter with no automatic retry. The
semantic hash covers only the documented fixture profile, not all possible
Blender state. No arbitrary files are opened to test their trustworthiness.

The fixed trusted Python entrypoint is deliberately supplied via CLI. Factory
startup, disabled automatic Python, offline preference, and isolated user
resources do not make Python or Blender's parser a security sandbox. Official
API/threading/Edit Mode/autoexec references and their implementation rationale
are recorded in `studio/blender-addon/README.md`.

Reproduce from the repository root with a new output name:

```powershell
python -B 8-9-hh3d-3/studio/tests/blender/run_blender_probe.py --output 8-9-hh3d-3/zdoc/reviews/20260917-gt04-blender-03
```

The source lane is frozen after `-02`; no engine/source changes are needed to
review this report. The coordinator must arrange any subsequent engine lease
and remint after source changes. No Godot/core/protocol/toolchain-lock/plan
source was modified by this worker, and no commit or tick was performed.
