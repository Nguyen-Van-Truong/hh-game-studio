# S49 final profile/bundle implementation review

AUTHORITY=0. Date: 2026-09-17. Implementation review only; no GT-03 acceptance, formal critic signature or tick.
Reviewer previously authored the script/scene grammar, so that portion is a self-review and cannot substitute for an independent acceptance critic.
Scope: factory → closed byte eligibility → fixed Linux profile driver → native observation comparison; complete bundle staging and claim boundaries.
No source edits, native storage mutation, engines, Docker or full test suite were run. Exact reviewed hashes are below; the seven primary files were unchanged on recheck.

## Result

No new concrete candidate-code injection or false-positive typed readback path was found in this bounded review.
The previous binary64 tiny-export comparison issue is closed: `profile_readback.py:45` defaults to zero epsilon, does not allow nonzero expected values to become zero, and applies `2e-6` only to native vector/basis values.
This conclusion supports continuing the frozen diagnostic runs; it does not establish sandbox acceptance, durable publication or arbitrary-GDScript support.

## Candidate execution and attribution

`fixture_profile.py:112` re-decodes the complete bundle, compares all nine fixed release/UID inputs to host-owned source pins, then checks the candidate scene/script grammar and resource UID collisions.
The two candidate-controlled source files cannot add a plugin, project setting, UID sidecar, preload, executable method, expression, static initializer, property hook, connection, inherited scene or external path.
The scene admits only Node3D/MeshInstance3D, one fixed root Script and unshared BoxMesh resources; quoted identifiers are positive ASCII grammars without escapes or terminators.
Script source is the full original bounded byte sequence, with fixed ordered export names, typed literal values and exactly native Node3D inheritance. Names cannot introduce callbacks or override native methods.
The shipped editor plugin is executable `@tool` code, but is separately pinned, not candidate-supplied. Its fixed preload chain is in the eleven-file closure.
`linux_executor.py:158` checks the complete input inventory, rejects nonempty preexisting cache and qualifies before any profile engine invocation. The fixed driver at line 192 executes parse, import and fresh readback as separate processes.
`validation_bootstrap.gd:115` can execute resource loading and instantiation; its safety argument depends on the preceding closed profile. It is not safe for arbitrary generated scripts and must not become a bypass entry point.
Successful output uses full-precision JSON at line 158. The comparator checks exact report shape, script source/disk/UID/type/reload/default observations, fresh script instance, declared SceneState properties and effective instantiated scene properties.
The profile runner requires the fixed phase sequence and one correctly positioned readback report alongside owned process/cleanup and unchanged-input evidence. Child text by itself remains untrusted.

## Pure independent checks performed

One isolated `python -B -` probe imported the frozen local modules without native constructors or engine calls; actual exit was 0.
It rejected 15 candidate variants covering `@tool`, `_ready` output injection, `_static_init`, same-line calls, comments, preload, script inheritance, setters, instanced/custom scene resources, unknown properties, connections and foreign resource paths.
It rejected four observation changes: boolean standing for integer, one binary64 ULP change in `move_speed`, wrong explicit float type and an unexpected script method.
A modified plugin with a newly self-consistent v2 manifest was rejected by the host factory; rehashing candidate metadata cannot replace pinned release bytes.
The saved baseline observation matched its expected eligible bytes and still returned `public_ack=false`, `process_attribution_proven=false`, `sandbox_acceptance=false`.
These are source-bound Python rejection/comparison observations, not new actual Godot evidence or a comprehensive hostile-language proof.

## Bundle/staging and remaining gates

`bundle_v2.py` preserves exact eleven-file bytes and JCS manifest identity; validation covers paths, roles, lengths, hashes and revisions. The role name `trusted` alone supplies no provenance; the factory supplies the release comparison.
`bundle_staging.py:205` reserves twelve objects against actual native inventory, stages manifest last, reads the entire set again and verifies the resulting inventory. Failed attempted writes retain UNKNOWN ownership instead of retrying.
Its exact retained receipt identity at line 277 prevents importing an invented `StageReceipt` as proof. Duplicate lookup is historical internal staging information; current bytes require explicit `readback`.
Staging accepts inert complete bundles rather than requiring eligibility. This is appropriate for byte storage, but a later executor/consumer must still call the factory; storage success never authorizes code execution.
Stager flags keep `public_ack`, `engine_effects_verified` and `namespace_durability_verified` false. Missing generic blob namespace durability, selection/adoption, durable receipts and restart write authority remain integration gaps.
The comparator deliberately accepts caller-supplied dictionaries and supplied bundle observation metadata. A fabricated matching report can pass a pure comparison; it cannot authenticate a process or engine SHA.
Likewise, the diagnostic bundle currently uses a source-file hash in the supplied `scene_revision` slot. It is explicitly not a freshly measured semantic scene revision and must not be promoted into a public save receipt.
A future coordinator must bind the actual pinned binary/source closure, immutable selected graph, fresh engine/editor readback and semantic revision before COMMITTED; copying the supplied engine/scene observations is insufficient.
The vector tolerance is approximate readback (`2e-6` relative/absolute), not byte-identical floating-point equality. Scalar exported floats retain exact binary64 comparison and explicit runtime type tags.
Source pins/module caches assume the frozen host release is trusted; Python dataclass immutability is not a boundary against malicious code already inside that host process.
None of these explicit limits waives plan §2.3, §2.5, TQ03 or TX09, and no full GT-03 result is inferred from this review.

## Exact reviewed source snapshot

Paths are relative to `8-9-hh3d-3/studio`. This is the review scope, not a replacement for the coordinator's full runtime source-closure manifest.

| Path | SHA-256 |
| --- | --- |
| `godot-addon/fixture_profile.py` | `25e1667dd930dcf0746b071fc29ea3460bc18d5fb9f3f83e806c1793028f21ae` |
| `godot-addon/profile_readback.py` | `14e4eaef581b12797e59b90a3510f8b90938d390cc8c5fe32ab0d218a90c9c1c` |
| `godot-addon/validation_bootstrap.gd` | `1e67888029b75945eb11d2730936e98a5028884d7746a4a2be9a7304cf5298cf` |
| `godot-addon/script_profile.py` | `0aff8d103982e56280b04ad4faca93cf3bd96d086016818daf7b3a432b4de7a5` |
| `godot-addon/scene_profile.py` | `7f37e6bba91e2729421a89c67f4507c198f80fa1420470a1e06524c2751d854c` |
| `godot-addon/bundle_staging.py` | `3d614edbec8e9a7f5ad3caf2b9694d7498df129de95683952268621f91d68e43` |
| `godot-addon/bundle_v2.py` | `2c5cdc71cdaf80f58bb93ec791e84bab8bd02cd4d9bdbd93d635db13583de62a` |
| `godot-addon/fixture_profile/source-pins.json` | `9a73a4e008092f22579399d1a6eef3c737d1db28b0cdb2dbe0471ffc1a707e56` |
| `godot-addon/fixture_profile/project.godot` | `2d4fa9c7261fc5ec4292094854ffa79b602249671a03db3c9808ea7521f4fa51` |
| `godot-addon/linux_executor.py` | `20e6a13b0e78a519d50ee253cf9f9aa9b04ee5429a00a689350f64f54ed05645` |
| `godot-addon/validator-toolchain.lock.json` | `f9a5400b04be557b40514321bbfea31c9bee627845636db85ffacb363fe4f71d` |
| `tests/godot/run_profile_probe.py` | `9941bf4f4a86ab1df03b9c9592b77da7b55a2ea1a309ddfefd86963b84422595` |

The pin manifest binds the nine installed content files; `trusted_files()` rehashed each during the isolated probe. No old critic signature was transferred to this snapshot.
