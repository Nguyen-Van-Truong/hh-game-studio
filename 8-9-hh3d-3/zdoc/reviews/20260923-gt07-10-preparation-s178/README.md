# GT07–GT10 preparation map — S178

Date: 2026-09-23 (Asia/Saigon)
Authority: 0 (preparation only; no checkbox, engine run, Android claim, or
dependency bypass)

This memo records useful existing implementation/test entry points so later
work can start from a bounded scope. It does not turn any prototype into an
accepted gate. GT07–GT10 remain blocked by the plan dependency on accepted
GT06, and GT08 still requires a physical Android device.

| Gate | Existing bounded scope | Evidence still required before opening the gate |
| --- | --- | --- |
| GT07 | Lease/recovery and publication state are present in `godot-addon/recovery_host.py`, `godot-addon/publication_recovery.py`, `host/blender/recovery_owner.py`, and `host/core/fixture_release.py`. Static recovery/transport suites exist. | A fresh GT07 run after GT06: two writers, FIFO/expiry/fencing, late result, crash/Stop recovery, actual process/job cleanup, and same-hash critics. |
| GT08 | Import/export and Linux/cleanup fixture tests exist, including `tests/blender/test_export_cleanup.py` and the protocol recovery suites. | Clean Windows + Linux headless + **physical Android** install/launch, pinned templates/ABI/page-size evidence, cache isolation, and actual exits. Emulator evidence cannot replace the device gate. |
| GT09 | Reviewer/client adversarial tests and client ledger/publication fixtures exist in `tests/reviewer/` and `tests/blender/`. | Full client conformance on the accepted GT07/GT08 fixture, real input path, transaction/recovery rows, no warnings/errors, and independent review. |
| GT10 | `host/core/fixture_release.py` and `tests/protocol/test_fixture_release.py` provide a starting release model. | Clean install, upgrade, rollback, revocation/security floor, uninstall preserving art/game, support manifest, and handoff package after GT09. |

## Exact source pins inspected

```text
07097a3e8d80cf84f8b5cae3288ad1fce8b10aca2fdac140a26555603c42ec16  studio/godot-addon/recovery_host.py
4ad678fc49826d4162ca8caac253bd4b8c50e6a6d9216cab9e5d6e35137b321d  studio/godot-addon/publication_recovery.py
6278691028120eca22b1966fcee113797a2a8b22ad5718fdc54612d586f72fad  studio/host/blender/recovery_owner.py
547a01252b7c5f31fba0655fec01e71039d094d6c328e3fa39428120bd464e47  studio/host/core/fixture_release.py
09e8e958fa437ad05d3169ffd60b12ffe5cf7d40802178e3e1e214a125194941  studio/tests/protocol/test_transport_recovery.py
a4953edbdfe49ef558990031471f7c0b8ce0c194cdf03359730bc57d2806d2d8  studio/tests/blender/test_export_cleanup.py
9417848b9544bec50ab4605e60baae8e5b2ddfca07f96f601a84d4a4d6e17cf8  studio/tests/reviewer/test_client_adversarial.py
```

## Operating rule

Do not run these suites beside a GT06 measurement, and do not label their
static presence as PASS. When GT06 is accepted, begin with GT07 using fresh
run and command IDs, then advance sequentially. If a required device or
dependency is unavailable, preserve the preparation and wait for that external
state rather than retrying an unchanged lane.
