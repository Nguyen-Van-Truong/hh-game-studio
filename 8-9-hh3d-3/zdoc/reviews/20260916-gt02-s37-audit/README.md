# S37 complete fixture release graphs — CANDIDATE

Frozen closure: `b4e007455f7fd0dce25f62433a8bb6a7717ef6ff765fe1b52bf6ddecd0275ab7`.
79 source files, 9 candidate artifacts. Protocol **236/240 passed + 4 explicit
skips**; bootstrap **56/56**. Actual process exits and owned trees passed, with
source/snapshot unchanged. Python/Node/Godot still agree on 2,396 canonical rows;
nine Godot invalid cases reject. No independent review or gate acceptance.

`fixture_release.py` implements a closed JSON fixture grammar (`value` and
explicit references), complete reachable-graph validation before staging,
private immutable blobs plus canonical manifest, project/store/file identities,
source/base-game revision metadata, and complete immutable readback pins.
This establishes completeness for the fixture grammar only, not Godot/Blender
resource dependencies. Staging remains separate from active selection.

The 12 new tests passed in the first focused run and in the complete candidate.
They cover no-write invalid input, missing/invented edges, duplicate/order/schema
faults, project/root/release substitution, corrupt/missing files, partial-stage
quota/verification failure, unchanged older snapshots, fresh-process whole
release pin and inert instruction-shaped values. Uncertain staging retains
files and poisons admission rather than claiming no effect or blindly retrying.

`diagnostic-manifest.json` binds 26 diagnostic files: the preserved S36 runs
(including the honest failed fixture run) plus S37 source/host/log records.
`verify_evidence.py` checks those hashes and source versions, candidate records,
process completion and requirement-to-passing-test mappings. Its S35 native
counter field explicitly verifies only the unchanged 73-file prior source
subset. That native run does not exercise S36 events or S37 release staging.

```powershell
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s37-audit/verify_evidence.py
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s37-audit/verify_git_bytes.py index
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s37-audit/verify_git_bytes.py HEAD
```

Git reconstruction checks exact source, candidate, diagnostic and previous
native-subset bytes using isolated Python. It does not rerun engines/native
clients; metadata states the actual checked commit. Public general safe_write
and atomic_replace remain unsupported.

Next: typed selector state/transactions on the retained event stream; durable
intent and whole-operation reservation before staging, source/game/fence CAS,
selection/readiness distinction, real mock-consumer adoption/readback, Stop,
explicit crash reconciliation, and actual confined-client integration. The
staging helper does not create those guarantees. Later engine mutation gates
and two independent reviews remain outstanding.
