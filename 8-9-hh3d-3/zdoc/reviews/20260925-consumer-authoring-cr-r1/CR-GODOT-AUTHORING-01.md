# CR-GODOT-AUTHORING-01 — shared gameplay script authoring

Revision 1, 2026-09-25. `AUTHORITY=0`; `STATUS=DESIGN_DRAFT`; `IMPLEMENTATION=NOT_STARTED`.
This is one proposed versioned tools change request for existing consumer rows
SA-T02 and H2-T01. It is not a new plan, gate, capability grant, or GT06 evidence.
The tools TXT remains the only tools progress source. GT06 and its frozen formal
source/profile remain unchanged; implementation of this extension follows the
GT10 maintenance/release route already specified by both consumer plans.

## Problem and intended result

The current managed `script_text.replace` path accepts only
`hh-godot-declarative-1`: `extends Node3D` and a closed list of exported scalar
variables. It rejects methods and property hooks. A command can change a speed
declaration, but it cannot author the controller that uses that speed. The scene
profile likewise accepts only Node3D/MeshInstance3D with private BoxMesh resources.
These are valid, scoped tools capabilities; they cannot support a claim that an
agent authored a complete 2D or HH World game through the public catalog.

The requested outcome is a reviewed, separately advertised profile through which
an agent can replace executable, typed gameplay source in a leased project and
publish its scene/script dependency closure together. An actual input replay must
show that the authored behavior changed. The same implementation serves 2D and
3D consumer fixtures, with separate evidence for each. The first thin fixture is
an integration milestone, not a reduction of either game's final requirements.

Current evidence pins are in `source-pins.json`. Static catalog defaults of
`implemented=false` do not mean every operation is unavailable: the managed
`GodotPublicationOwner.discovery()` explicitly enables its registered backends.
Availability claims must name the owner, profile, version and native evidence.

## Contract to settle before implementation

- Owner: Godot adapter/script-authoring maintainer; coordinator assigns one writer
  lease and the exact source closure when dispatch becomes eligible. Consumers:
  SA-02/SA-03 and H2-P0-03. Proposed profile name:
  `hh-godot-gameplay-source-1`; this name is not currently advertised.
- Preserve the accepted declarative profile and its negative tests. Do not grow
  its grammar into a second GDScript interpreter or silently widen an existing
  capability. Introduce a distinct profile and catalogue digest with explicit
  compatibility and install/rollback tests.
- Reuse the shared Request envelope, `script_text.replace`, command digest,
  lease/fence, scene/project revisions, Stop and durable receipt path. Select the
  profile through trusted registered owner configuration, not a request flag that
  enables execution. Bind every script path to a host-approved project manifest;
  do not accept an arbitrary absolute path or evaluator method.
- The complete candidate graph includes scene, scripts, UID sidecars, local
  imports/preloads/resources and approved project settings. Missing or escaping
  dependencies reject before activation. Store original bytes and hashes; native
  parsing/readback must observe those bytes, not a rewritten approximation.
- Runtime methods are allowed only in the new profile. `@tool`, editor plugins,
  GDExtension, native libraries and custom importers stay outside this request.
  Runtime code is still untrusted during import, static initialization and Play.
  Syntax/type success is not an isolation proof. OS-enforced filesystem/network
  confinement, secret-free environment and bounded owned-process execution must
  protect both validator and disposable Play; substring bans are not a sandbox.
- Scene/script edits form one candidate project revision. Native validation,
  complete semantic readback and journaled activation must precede COMMITTED.
  A changed manual revision must preserve both versions and return conflict.
  Crash/Stop/lost response reuses journal lookup, never blindly repeats effects.
- The existing 16 KiB script bound is a starting constraint to evaluate, not a
  silent new limit for a full game. Freeze module count, per-module bytes, total
  closure size, CPU/RAM/disk/wall limits and result caps before new-profile code.
  Larger projects require explicit measured profile versions, not hidden caps.

The containment and complete-load-graph design is the first implementation
decision. Reusing existing private fixture assumptions for general scripts would
be an unsafe and unmaintainable shortcut.

## Affected implementation and regression map

All paths below are relative to `8-9-hh3d-3/studio/`. They are candidate affected
paths for a later lease, not permission to edit the frozen formal source now.

| Area | Existing boundary to reuse | Expected new work / required regression |
| --- | --- | --- |
| Discovery and request validation | `godot-addon/operations.json`, `contract.py`, `publication_session.py` | Add separately enabled profile; old callers keep old semantics. Extend `tests/godot/test_contract.py` and `test_publication_session.py`; unknown/disabled profile is a no-effect reject. |
| Script and complete graph eligibility | `godot-addon/script_profile.py`, `scene_profile.py`, `fixture_profile.py`, `bundle_v2.py` | New gameplay-profile/graph module; retain old profile unmodified where possible. Add `tests/godot/test_gameplay_source_profile.py` (proposed). Preserve `test_script_profile.py`, `test_scene_profile.py`, `test_bundle_v2.py` rejection coverage. |
| Native validation and isolation | `godot-addon/linux_executor.py`, `validation_owner.py`, `profile_readback.py` | Extend registered validator for the new graph and typed readback. `tests/godot/test_validation_owner.py` already covers changed source, forged/foreign receipts, raw phase order, cleanup and cancellation; extend those cases rather than invent a parallel receipt format. |
| Publication / recovery | `godot-addon/publication_owner.py`, `publication_journal_v5.py`, `publication_state_v5.py`, `protected_bundle.py` | Atomic complete-graph activation and owner-edit conflict; extend `tests/godot/run_script_publication_probe.py` and `run_recovery_cut_matrix.py` with the new profile. Keep old profile evidence tied to its original closure. |
| Runtime behavior proof | `host/replay/contract.py`, `backend.py`, `inspector.py` | Use separately versioned SA-T03/H2 runtime capability; retained inspection remains labelled historical. Add `tests/conformance/run_gameplay_authoring_probe.py` (proposed), only after its runtime dependencies exist. |

Proposed new test paths do not exist yet and do not constitute passing tests.
The initial source pins identify inspected files only; they are not a complete
runtime closure and cannot authorize execution.

## Acceptance cases for the new profile

1. **AUTH-01 — authored behavior:** obtain the real registered catalog, lease and
   project revision; send a public script replacement that changes a controller's
   response. Replay the same real input before/after and observe a corresponding
   displacement/state change. No hidden shell write of the tested source, direct
   runtime state injection, or pre-authored expected-result switch.
2. **AUTH-02 — dependency closure:** multi-script preload and script/scene binding
   read back correctly after save, close and reopen. Missing, stale-hash, UID
   collision, cyclic-unbounded or outside-root inputs reject before activation.
3. **AUTH-03 — failure preserves last good:** syntax/type error, unsupported
   `@tool`/native dependency, validator crash, timeout, output cap and Stop each
   keep the prior active revision. The exact raw reason, actual exits and owned
   jobs/handles are retained. Partial validation never returns COMMITTED.
4. **AUTH-04 — idempotence and recovery:** cut before/after each durable publish
   phase and ACK. Restart/lookup returns the durable outcome; same ID and digest
   never duplicates an effect, same ID with changed source conflicts. A concurrent
   manual edit is preserved and exposed for reconciliation.
5. **AUTH-05 — isolation:** trusted negative test sources attempt an out-of-root
   file effect, process spawn, network access and unbounded startup/Play work in
   the disposable environment. OS observations must demonstrate the policy or
   return UNSUPPORTED; the test must reach the intended fault, not fail earlier
   because of a syntax/path setup error.
6. **AUTH-06 — two consumers:** run separate original 2D and 3D fixtures through
   menu/input/behavior/pause/resume/quit with PID/source/time binding, native
   readback and actual exit/owned-tree proof. 2D node/input capability is a
   prerequisite, not implied by script support. These fixtures are not game
   parity, multiplayer, fun, art-quality or release acceptance.
7. **AUTH-07 — delivery:** new package install/upgrade/rollback passes on a clean
   consumer copy, preserves source/save data, keeps the declarative profile
   compatible, and has two independent critics on the same final closure.

## Remaining consumer gaps and efficient sequencing

This request closes only shared executable-source authoring. SA-T01 still owns
typed 2D scene/physics/UI/audio resources; SA-T03 owns 2D input/observation;
SA-T04 owns sprite/atlas/animation/audio intake; SA-T05 owns Web export/browser
proof. H2-T02 owns controller/camera/collision bindings, H2-T03 public
mesh/rig/skin/clip authoring, and H2-T04 UI/audio/activity/save bindings.
SA-T06 depends on actual reference/mobile requirements. Keep those existing IDs.

After the GT10 package exists, implement shared source/transaction support once,
then the smallest genuinely useful 2D and 3D capability sets needed by the first
consumer WPs. Exercise both consumers before broadening operations. Reuse the
accepted protocol, journal, protected storage and process owners with affected
regressions; avoid a second generic execution protocol. Blender is useful for
3D assets and optional sprite production, but forcing every 2D sprite through
Blender creates work without establishing gameplay capability. Full game quality
still requires each product plan's runtime, target, content and human evidence.

During GT06, permitted work on this request is source/contract inspection and
preparation of these cases. Opening implementation, engine probes or capability
advertising here would bypass the current dependency policy. The coordinator's
primary execution effort stays on the unresolved GT06 boundary.
