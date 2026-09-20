# S132 current replay dependency inventory

2026-09-20. AUTHORITY=0; bounded read-only preparation, not a final critic or
acceptance verdict. No source edits, imports of product modules, tests, engines,
live-run reads, or source/evidence hashing. This file is the only output of this
follow-up. Counts below are path-set comparisons, not current hash verification.

Use the historical maps as path seeds, then mint a new fixed execution binding
from current bytes after the host diagnostic is terminal and cleanup is known.
Do not edit GT05/S69/S79 manifests or substitute new hashes into old evidence.
Asset provenance and current execution provenance have different roles.

## Existing maps and the complete known conservative union

| Set | Exact source / loader | Observed path count and limitation |
| --- | --- | --- |
| GT05 accepted seed | `zdoc/reviews/20260917-gt05-s63-audit/manifest.json#/source_files` | 143 paths; remove the exact `8-9-hh3d-3/studio/` prefix when forming a studio-relative map. This includes historical test/docs paths; do not silently narrow it while preserving the old closure claim. |
| S69 native runtime seed | `studio/.local/reviews/gt06-s69-managed-replay-01/source-files.json` | 159 paths = GT05143 +16 native/profile/observe paths. Historical metadata only was read. |
| S69 replay verifier | Same run's `repair-replay.json#/verifier_sources`; `host/replay/repair_replay.py:18-20` | Four bare filenames: repair_replay.py, repair.py, observation.py, trace.py. Prefix `host/replay/`; trace already belongs to runtime159, so combined path set is162, not163. These are verifier dependencies, not a full managed editor stack. |
| S79 backend seed | `zdoc/reviews/20260918-gt06-s79-diagnosis/service-remint-01/freeze.json#/backend_source_files` | 174 paths. `backend.PreparedPlay.prepare():51-59` adds all current `host/replay/*.py` plus `contracts/perf-collector.schema.json` to native sources. Current directory has no Python filename absent from S79's174, before any new binding-reader integration. This says nothing about byte equality. |
| Current GT03 declared release domain | `godot-addon/validation_owner.py:73-103`, `_SOURCE_SUFFIXES` at27 | 80 paths: explicit toolchain.lock.json and build/bootstrap/run_fixture.py, plus recursive godot-addon, host/core and protocol files with .py/.gd/.uid/.cfg/.godot/.json suffixes, skipping __pycache__. Filename-only enumeration both with rg and without ignore rules agreed at80. Do not execute `source_release()` during a live measurement; it hashes the domain. |
| Conservative shared execution inventory | S79 backend174 union current GT03 release80 | 213 distinct studio-relative paths today; 39 GT03 paths are absent from S79 backend. This covers the known native/backend/managed-repair code and declared GT03 release inputs. Add the forthcoming binding reader, selected lane driver/launcher/verifier and their transitive dependencies explicitly. Keep imported stdlib/runtime and binaries in separately bound toolchain provenance. |

S79 backend174 minus S69 runtime159 contains these15 paths. Three are supplied
by S69's separate verifier map (observation, repair, repair_replay); the other12
remain absent from the combined S69 runtime+verifier path set:

```text
contracts/perf-collector.schema.json
host/replay/backend.py
host/replay/contract.py
host/replay/disk_journal_index.py
host/replay/inspector.py
host/replay/journal_index.py
host/replay/observation.py
host/replay/perf.py
host/replay/perf_export.py
host/replay/repair.py
host/replay/repair_replay.py
host/replay/service.py
host/replay/session.py
host/replay/transport.py
host/replay/verified_journal.py
```

The39 current GT03 release paths absent from S79 backend174 are:

```text
godot-addon/addons/hh_studio/plugin.cfg
godot-addon/addons/hh_studio/plugin.gd
godot-addon/addons/hh_studio/scene_commands.gd
godot-addon/bundle.py
godot-addon/bundle_staging.py
godot-addon/bundle_v2.py
godot-addon/contract.py
godot-addon/editor_owner.py
godot-addon/fixture_profile.py
godot-addon/fixture_profile/addons/hh_studio/jcs_godot.gd.uid
godot-addon/fixture_profile/addons/hh_studio/plugin.gd.uid
godot-addon/fixture_profile/addons/hh_studio/scene_commands.gd.uid
godot-addon/fixture_profile/project.godot
godot-addon/fixture_profile/scripts/fixture_actor.gd.uid
godot-addon/fixture_profile/source-pins.json
godot-addon/linux_executor.py
godot-addon/operations.json
godot-addon/profile_readback.py
godot-addon/protected_bundle.py
godot-addon/publication_fifo.py
godot-addon/publication_journal.py
godot-addon/publication_journal_v2.py
godot-addon/publication_journal_v3.py
godot-addon/publication_journal_v4.py
godot-addon/publication_journal_v5.py
godot-addon/publication_owner.py
godot-addon/publication_recovery.py
godot-addon/publication_session.py
godot-addon/publication_state.py
godot-addon/publication_state_v2.py
godot-addon/publication_state_v3.py
godot-addon/publication_state_v4.py
godot-addon/publication_state_v5.py
godot-addon/publication_transport.py
godot-addon/recovery_host.py
godot-addon/scene_profile.py
godot-addon/validation_bootstrap.gd
godot-addon/validation_owner.py
godot-addon/validator-toolchain.lock.json
```

These are missing from the declared historical maps; they are not claimed to
have been newly created since S69/S79. Some belong to GT03's conservative
declared release even if a particular repair does not exercise their branch.
Conversely, `godot-addon/publication_transport.py` is directly executed by the
backend service transport: `host/replay/transport.py:26-29` dynamically loads
it, despite its absence from backend174. Restricting an audit to old map keys
would miss this dependency without any newly added Python filename.

`godot-addon/cli_job.py`, `host/core/transport.py` and
`build/bootstrap/run_fixture.py` are already in GT05143/S69/S79. They are not
missing-path additions. Git name/status comparison against GT05 checkpoint
808d8ba records modifications to the first two (besides added observe files);
current plan also identifies those changed shared dependencies. No digest
comparison was performed here. Current `native_runner.sources():85-89` rightly
raises `REPLAY_REUSE_SOURCE_CHANGED` on mismatched old GT05 source hashes.
Retain that fail-closed principle when switching to a new execution binding.

## Concrete loader and input graph

| Entrypoint / edge | Files or maps that must remain bound |
| --- | --- |
| `native_runner.accepted_inputs():69-79` | Reads the external-to-studio `zdoc/reviews/20260917-gt05-s63-audit/manifest.json`, checks its fixed `MANIFEST_SHA`, then checks raw hashes for exactly consumer.INPUTS: `.local/reviews/gt05-validation-s62-01/fixture.glb`, manifest.json and producer-report.json. Keep this historical asset check separate from current executable-source binding. |
| `native_runner.sources():82-99` and `prepare():115-132` | GT05 seed plus recursive .gd/.uid/.godot/.tscn/.tres under godot-addon/observe and fixtures/play-observe; script_profile.py; native_runner.py, process_probe.py, trace.py, profile.json. Also copies pipeline/godot/authored.gd and authored_material.tres (already in GT05), fixed imported GLB preset, trace/config and run-specific binding. |
| Native process supervision | `pipeline/native_job.py` imports host/blender/ui_host.py and export_job.py. ui_host.load():25-36 dynamically loads blender-addon/ipc_client.py and godot-addon/cli_job.py. HELPER is an inline string in ui_host.py; pin that containing source. Existing GT05 map covers these plus core/protocol imports; enumerate current transitive additions before freeze. |
| Backend/service | `PreparedPlay.prepare` extends native source domain with all replay Python and perf schema; ReplayService imports VerifiedJournal -> DiskJournalIndex. ReplayTransport dynamically loads godot-addon/publication_transport.py -> core transport/limits/redaction/protocol. A new binding reader under host/replay will be captured by the backend glob but must also be in the fixed dependency binding if consumed by native/repair entrypoints. |
| `repair.main():211-231` | Starts from native sources + repair.py + observation.py, copies source map, then dynamically loads build/bootstrap/run_fixture.py and calls its run_process for the child. Bootstrap wrapper is already in the seed but is an execution dependency, not merely audit metadata. Parent/child/request closures must cover the actual launcher and Python executable too. |
| `repair.execute():76-91` | Dynamically loads godot-addon/publication_owner.py; `_load('validation_owner')`; then GodotPublicationOwner.create loads contract, publication_session, editor_owner, validation_owner, publication_journal_v5, publication_fifo. PublicationTransport is separately loaded for HTTP mutation. Include transitive earlier journal/state versions and recovery/protected-bundle modules through the declared GT03 source release. |
| GT03 factory/editor/validator | validation_owner._load loads profile_readback -> fixture_profile -> bundle_staging -> bundle_v2. `_loaded_release():116-144` checks scene_profile, script_profile, cli_job; editor_owner._release():72-81 binds factory/profile modules, core/protocol, toolchain and all fixture source pins. `fixture_profile.trusted_files():74-93` verifies fixed source-pins.json plus the nine source paths in `_SOURCES`, including protocol/jcs_godot.gd. Use this function after measurement to validate pins; a Python-import scan alone does not find these files. |
| Linux validator external files / toolchain | linux_executor._profile_harness() reads godot-addon/validation_bootstrap.gd; `_lock():379-394` reads validator-toolchain.lock.json; `_owned_runner():407-413` reads/checks/imports build/bootstrap/run_fixture.py. Preserve existing hard pins for those bytes, Linux Godot binary, Docker image/supervisor and desktop context. Windows editor binary comes from toolchain.lock.json. Environment-selected Linux binary still must satisfy its fixed binary hash; it is not a source-path escape. |
| `repair_replay.run():76-103` | The four verifier-source map plus native current execution binding; reads immutable selected repair capture/source copies/config and fault capture/runtime snapshots through verified_repair and verified_fault. Reusing a verified old repair receipt does not execute the GT03 mutation stack again. A fresh managed editor repair does, and needs the full GT03 declared domain above. Preserve causal input hashes independently of current source hashes. |
| Lane launchers | Add exact `tests/replay/run_service_probe.py` or run_service_adversary.py and outer launcher when invoking service lanes; the latter dynamically imports build/bootstrap/run_fixture.py. GUI lanes additionally require reviewer sources and tests/reviewer/run_reviewer_probe.py. These execution drivers are not established by backend174 alone. Benchmark source_files/load_fixture are a different closure; never use the campaign53 map as a substitute for backend/repair. |

## Minting without a self-referential hash

If native_runner embeds the new binding JSON's exact SHA, do not include
native_runner's resulting hash in that same binding's source map. The cycle
would be `binding SHA -> literal in native_runner -> native_runner SHA ->
binding SHA`, requiring a cryptographic fixed point. The binding artifact must
not include its own hash as one of its dependencies either.

Use an acyclic split with explicit semantics:

1. Freeze a dependency binding for the known execution dependency subset,
   excluding only files that embed that binding's digest and the binding JSON
   itself. Pin the reader's final source if it has no back-reference. Record the
   exact exclusion list and reason; do not call this subset the complete run
   source closure. Validate duplicate keys, path normalization/root containment,
   required-file set, lowercase SHA format, binding schema and actual bytes.
2. Mint immutable JSON from those current dependency bytes. Preserve the fixed
   accepted GT05 manifest/hash and raw asset checks as independent provenance;
   do not reinterpret that manifest's old source map as current acceptance.
3. Set native_runner's fixed digest to this binding. Then freeze the independent
   request/run closure including final native_runner, the binding JSON, reader,
   dependency set, selected launcher/verifier, and external consumed manifest
   in an explicit parent-root evidence domain. If root is studio, represent the
   external manifest separately with a fixed verified path/hash; never allow
   `../` to evade the source-map path guard.
4. Import/prepare only against that final closure, and independently check it
   before launch and after completion. Run-specific immutable project files,
   trace/config and input/run.json are layered onto the runtime closure after
   source closure is fixed, as current native/backend code already does.
   This protects the excluded digest consumer through the run/request closure
   without reintroducing a binding fixed point.

After the current diagnostic, the coordinator can use the precise path union
above plus new reader/driver additions to mint current hashes once. Then call
the GT03 loader/pin functions in a fresh, owned verification context to confirm
that the declared80-path release and dynamically imported modules match the
frozen set; recompute and fail if the union adds a path. Loader imports may
hash source at import time, so they were deliberately not run in this review.
Existing `native.sources(accepted)` cannot be used as a mint helper while it
still requires the old GT05 source digests; reading map keys and enumerating
the current declared domains is preparatory input, not bypassing the runtime
guard. No binding, source hash, test outcome, native exit or new acceptance is
asserted by this document.
