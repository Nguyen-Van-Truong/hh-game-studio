# S49 managed profile implementation cross-review

AUTHORITY=0. IMPLEMENTATION_REVIEW_ONLY=1. ACCEPTANCE_VERDICT=NONE.
ENGINE_RUNS_BY_THIS_REVIEW=0. PLAN_TICK=NONE.
Date: 2026-09-17, Asia/Saigon. Baseline Git HEAD:
`e09f7806a6e3198e82c4ac1dd42dffd342531ef5`.

The review found scalar readback and raw-evidence admission defects. The
coordinator corrected them; the focused pure regressions below now pass.
No additional concrete candidate-code/dependency injection was established
within the inspected closed grammar. This conclusion covers implementation
logic and the stated pure tests, not a formal GT-03 acceptance or the
coordinator's subsequent complete frozen engine run.

## Scope and source identity

Reviewed factory, scene/script eligibility, fixed GDScript readback, comparator,
Linux profile input/command/mount policy and raw-evidence evaluator. Source was
being integrated by the coordinator during this bounded review. The scene
worker explicitly froze `scene_profile.py` at `7f37e6b…`; this reviewer did not
edit any implementation file. The coordinator additionally assigned the one
new `tests/godot/test_profile_probe_evidence.py`, which this reviewer wrote and
froze. The only other authored file is this report.

These are the selected hashes captured unchanged before/after the final
17-test evidence regression run, paths relative to `studio/`. This list is a
review scope manifest, not a complete interpreter/native execution closure.

| File | SHA256 |
| --- | --- |
| `godot-addon/fixture_profile.py` | `25e1667dd930dcf0746b071fc29ea3460bc18d5fb9f3f83e806c1793028f21ae` |
| `godot-addon/fixture_profile/source-pins.json` | `9a73a4e008092f22579399d1a6eef3c737d1db28b0cdb2dbe0471ffc1a707e56` |
| `godot-addon/scene_profile.py` | `7f37e6bba91e2729421a89c67f4507c198f80fa1420470a1e06524c2751d854c` |
| `godot-addon/script_profile.py` | `0aff8d103982e56280b04ad4faca93cf3bd96d086016818daf7b3a432b4de7a5` |
| `godot-addon/validation_bootstrap.gd` | `1e67888029b75945eb11d2730936e98a5028884d7746a4a2be9a7304cf5298cf` |
| `godot-addon/profile_readback.py` | `14e4eaef581b12797e59b90a3510f8b90938d390cc8c5fe32ab0d218a90c9c1c` |
| `godot-addon/linux_executor.py` | `a564ac8183eb715809ea82575f2050dc383cde8d071404f4e43d8465f9096205` |
| `godot-addon/cli_job.py` | `da93593e8bf0cac6d26904322f81ebfe77f46de8c882c23f887e2b4fe28cdacb` |
| `tests/godot/run_profile_probe.py` | `9941bf4f4a86ab1df03b9c9592b77da7b55a2ea1a309ddfefd86963b84422595` |
| `tests/godot/test_profile_probe_evidence.py` | `4640ea3e22824bb2dbaec49d2a4bf2f32eb0212a3dae2f037a68b2de49f2de3d` |
| `tests/godot/fixtures/profile-readback-baseline.json` | `5b65173a7d1d8eb584b81922ad178ca5726ac58b1018e414c5886e5333411b9c` |

Later coordinator edits, including additional native cases or cleanup changes,
need their own complete freeze; this report does not silently relabel those
bytes as the above tested snapshot.

## F1 — P2, fixed: scalar tolerance collapsed admitted nonzero values to zero

**Location:** `godot-addon/profile_readback.py`, `_equal`, lines 45–49.
Originally reviewed hash:
`323eb0c49573222ad6942ce6440d351e77315232aa76cd68de0b10c2be0f8c14`.

The scalar branch used absolute and relative tolerance `1e-12`. The declarative
grammar permits nonzero binary64 values smaller than that absolute floor.
This reviewer constructed an eligible script containing
`@export var move_speed: float = 0.0000000000001`, adapted the saved baseline
observation's source hashes and defaults to that script, and changed only the
reported scene instance's `move_speed` to `0.0`. Both the correct synthetic
report and the wrong-zero report returned `PROFILE_OBSERVATIONS_MATCH`.
The default and fresh-instance reports still contained `1e-13`, so this was
not simply a matching fabricated input/expected-value pair.

This was a pure comparator repro, not an assertion that Godot produced the
wrong zero. Its significance is that the verifier could not distinguish that
wrong native result for an explicitly admitted value.

**Correction checked:** scalar values now compare with zero epsilon against
full-precision binary64 JSON values; vector/basis handling remains separate.
A nonzero expected value cannot match zero, including on the vector path.
The coordinator's dedicated `test_tiny_admitted_export_cannot_collapse_to_zero`
passed in the 102-test run below at readback hash
`b9146c89b4e0d7955a427a57903b322f640179ccc889643f19d31b4d549053ba`.
The final table's later readback retains that fix and adds native SceneState
path spelling correction. Native tiny-value behavior still belongs to the
coordinator's fresh engine proof, not this pure regression.

## F2 — P2, fixed: raw-evidence lifecycle and marker facts were too permissive

**Location:** `tests/godot/run_profile_probe.py`, `evaluate`, lines 33–89.

The first implementation collected phase lines and readback markers
independently, without requiring the report inside its readback phase. Numeric
equality also let Python booleans/floats stand for native integer zero/one.
Those two issues were identified by inspection and fixed before the first
captured run of this review's new tests. Their negative regressions now pass.

The first captured new-test run, against evaluator hash
`6052a2b15dd6ca2287e7d8642ee8fedb2565967494548d70b38fe14203f20aa9`, still
reproduced **17 failing subcases across three tests**:

* Missing or dirty native Job owner facts could coexist with a passed result.
  A changed `closed`, `zero_observed`, `tainted`, `handle_retained`, or missing
  owner object did not invalidate the trusted-looking clean flag.
* Missing `timed_out`/`stream_cap_exceeded`, integer zero in those boolean fields,
  and numeric one in the EOF array could be accepted through truthiness/equality.
* A wrong executor schema or mode (`parse`/`import`) could be transplanted into
  otherwise valid profile evidence without rejection.

These are evidence-verifier defects. The repro uses an explicit synthetic
lifecycle record and saved observation data; it is not a claim that a candidate
script can forge Docker/native process facts in the current closed grammar.

**Correction checked:** the final-table evaluator requires exact schema/mode,
typed integer exits/PIDs/counts, explicit booleans, completed EOF, a checked
closed native Job owner with zero observed/no taint/no retained handle, exact
eleven-file hashes, the current fixed-helper hash and a single report between
readback begin/end. It recomputes the pure comparison from duplicate-key/NaN
rejecting parsed raw JSON. All 17 focused tests passed after these changes.

The tests also cover missing/reordered/duplicate/nonzero phase records;
missing/duplicate/malformed reports; unknown or stale file hashes; missing
exit/wait facts; unchanged flags versus actual errors/OOM/live PID; wrong UID,
script hash or instance values; helper mismatch; warnings/errors/leaks in
either stream; and a stale report despite lifecycle hashes matching a new
script bundle. The positive fixture explicitly remains replay data plus
synthetic host facts, never newly executed engine evidence.

## Other reviewed boundaries

The candidate grammar is positive and complete, rather than keyword filtering.
Script bytes permit only `extends Node3D` and the four fixed typed literal
exports in fixed order. Static initializers, `@tool`, methods, setters/getters,
expressions, loads, script inheritance, comments and escaped payloads have no
accepted production. Scene bytes admit one fixed external Script attached to
the root, bounded Node3D/MeshInstance3D nodes and unshared local BoxMesh data.
Unknown fields, groups, connections, instances, inheritance, embedded scripts,
other resources and extra paths are rejected. The host never calls a general
Godot parser merely to decide whether these bytes are eligible.

The factory replaces candidate authority with exact installed release bytes:
fixed project configuration, plugin configuration/source, protocol source and
four retained UID sidecars. A caller-rehashed manifest cannot substitute those
bytes. The script-side UID is canonical and range checked; an explicit external
UID must agree. The factory also rejects duplicate sidecar UIDs and a scene UID
colliding with any of the four sidecars. Release-source custody against a
concurrent same-user host attacker is not asserted by this factory.

Scene numeric metadata separates a serialized integer Variant assigned to a
float export from its effective typed float instance value. Integer/bool types
remain distinct. Decimal bounds are checked before conversion; nonzero
underflow and nonfinite values reject; vector/basis values round to stock
binary32. Transform comparisons preserve row/origin ordering. The documented
binary32 epsilon is not reused for exported binary64 scalar values after F1.

Linux profile admission checks all eleven exact source paths, pins the trusted
subset through the factory and rejects populated caches before making output.
The read-only snapshot contains those eleven bytes. The independently pinned
fixed helper is copied into a separate read-only `/harness` bind, checked before
start and after completion. The driver uses fixed parse/import/readback argv,
sequential phases, fail-fast nonzero exits, a shared container/cache, and the
existing namespace-PID-1 deadline and resource policy. It does not accept a
candidate entrypoint, harness, argv, Docker context or extra mount.

The helper compares script source/disk hashes, retained/resource UID, absence
of tool/base/global/method/signal/constant behavior, defaults, a fresh script
instance, serialized SceneState and instantiated hierarchy/export values. Host
raw-evidence comparison binds those observations to all input hashes and the
fixed helper; it does not treat the child's status string alone as a result.

A pure sizing probe constructed an eligible 64-node/63-BoxMesh graph with
48-character node names, deep parent paths, long resource/stable IDs and
nontrivial numeric values: scene 76,974 bytes, compact expected state plus
instance JSON 207,552 bytes, below the 262,144-byte stream cap. This was a
bounded example, not a proof of every native maximum-size serialization and
not a native engine run; no size defect was demonstrated.

## Actual checks and retained failures

1. Existing pure script/scene/readback/Linux-profile tests: **102 passed**,
   actual child exit 0, 1.003 seconds, explicit 30-second subprocess timeout.
   Twelve selected source hashes were unchanged. This run included the scalar
   fix but preceded the final evaluator and later SceneState path correction.
2. New raw-evidence suite first run: actual exit **1**, 17 tests with 17 failing
   subcases, 0.359 seconds. Full stdout/stderr and before/after hashes retained
   at `C:/Users/truon/AppData/Local/Temp/hh-s49-profile-evidence-tests-01-w5x1ytnp/`.
3. New raw-evidence suite after coordinator corrections: **17 passed**, actual
   exit **0**, 0.263 seconds, explicit 30-second timeout; the eleven source
   hashes in the table were unchanged. Logs/capture/manifests retained at
   `C:/Users/truon/AppData/Local/Temp/hh-s49-profile-evidence-tests-02-dvw39yfq/`.
   Command: `python -B -m unittest test_profile_probe_evidence -v`, cwd
   `studio/tests/godot`. No Docker or Godot was launched by either run.

The coordinator's `20260917-gt03-s49-profile-01/capture.json` was read, not
executed by this reviewer. It records actual target exit 1, wrapper exit 0,
tree verified, frozen snapshot unchanged but working source changed. Only
`defaults_override` passed; `transformed_box` and `typed_scene_override` failed
comparison. The coordinator corrected expected non-root SceneState paths to
retain their `./` prefix (distinct from instance paths). That historical
package remains failed. A later actual frozen run must establish the corrected
native comparisons, including nested paths and tiny exports; these pure tests
cannot relabel -01 as passing.

No remaining concrete open defect was established in this bounded review
after the identified corrections. Remaining native profile coverage and the
coordinator's complete source/engine proof remain separate work; no formal
acceptance signature, plan tick or runtime availability is issued here.
