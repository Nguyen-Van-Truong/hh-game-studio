# GT-01 source-closure audit (r13)

Status: **CANDIDATE** (candidate evidence; not acceptance)

This is a read-only audit of the files required to reproduce the GT-01 runner/bootstrap and both sample fixtures. Paths are repository-relative; no host root is recorded.

## Required closure

| Path | State | SHA-256 | Size |
|---|---|---|---:|
| `8-9-hh3d-3/studio/toolchain.lock.json` | OK | `57378d25ac7f673f94d325f422a9324e626620e0132fa34d5d040695f83be0c2` | 3090 |
| `8-9-hh3d-3/studio/build/bootstrap/run_fixture.py` | OK | `16d2c7c85eb69fac0d0189c4c845dde4b89c3d050cab3fb8a5886b07d4a3abf0` | 25513 |
| `8-9-hh3d-3/studio/build/bootstrap/install_toolchain.py` | OK | `fb47d31908291c8429279f54844623368d77854f84c6589795fa47ae4c60d366` | 21763 |
| `8-9-hh3d-3/studio/build/bootstrap/verify_archive.py` | OK | `754a5d9998055252de982e4f24b7bd581841755821c5f32f2776160152592f8b` | 9891 |
| `8-9-hh3d-3/studio/fixtures/sample-game/project.godot` | OK | `47a17c6038e7e43e90c46647642faa8e7547381601c484306d9ef2f953157dee` | 559 |
| `8-9-hh3d-3/studio/fixtures/sample-game/main.tscn` | OK | `194adf560f792e15a0db062ec2d436db4f15569e709da9a976b913a6c1307b42` | 276 |
| `8-9-hh3d-3/studio/fixtures/sample-game/scripts/main.gd` | OK | `688827516b16e31162b191b6b23bbfe2a90801fd54499ae2c81766ce9b2b044e` | 3153 |
| `8-9-hh3d-3/studio/fixtures/sample-game/scripts/main.gd.uid` | OK | `5fc2d82e403a8b31fe608c6a2bf971396d98f3f26341948cf248b563b143b568` | 20 |
| `8-9-hh3d-3/studio/fixtures/sample-game/scripts/trace.gd` | OK | `d24719e1f6e80dfd2961d86f58b1d03e0a315b1f1664528aea54fa4385408ae8` | 4797 |
| `8-9-hh3d-3/studio/fixtures/sample-game/scripts/trace.gd.uid` | OK | `87010b6fd149d35fc52dcf29bfaffde8a0cffb1d472f6ba3796ea5bcfc9f4d78` | 20 |
| `8-9-hh3d-3/studio/fixtures/sample-blender/create_fixture.py` | OK | `01403514c6779b1ae8df995af3aae84437b7032e7a2aecc5aa2acfcbee62743a` | 4199 |

## Freeze gaps

- None detected by this audit.

## Generated/cache observations

- `8-9-hh3d-3/studio/.local` (generated_directory)
- `8-9-hh3d-3/studio/build/bootstrap/__pycache__` (generated_directory)
- `8-9-hh3d-3/studio/evidence` (generated_directory)
- `8-9-hh3d-3/studio/fixtures/sample-blender/__pycache__` (generated_directory)
- `8-9-hh3d-3/studio/tests/bootstrap/__pycache__` (generated_directory)

## Limits and next gate

- read-only lexical/lstat/hash audit; no race-proof open-handle guarantee
- does not execute Godot, Blender, installer, or runner
- does not prove archive/binary hashes or runtime dependency closure
- secret scan is conservative pattern matching, not credential validation
- generated/cache presence is a freeze gap but files are not deleted

GT-01 still requires one frozen source hash, official serial runtime evidence, archive/installer recovery evidence, TQ01/TX12/TX14 checks, and two independent critics. This report cannot tick the plan.
