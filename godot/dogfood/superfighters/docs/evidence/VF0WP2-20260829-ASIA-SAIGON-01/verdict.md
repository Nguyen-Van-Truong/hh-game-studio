# VF0-WP2 verdict

PASS resource hygiene on working tree after VF0-WP1 freeze
`be77f95` / tick `cf2c7fe`. Not Y8 parity. Not V0. Plan checkbox **not** ticked.

## DoD / Verify (quoted)

Verify: headless `--verbose` has no `Leaked instance`, `Resource still in use`,
or `ObjectDB instances were leaked`; exit 0; functional labels still PASS;
repeat 3 times with identical normalized output hash.

DoD: clean teardown, or a gap report with reproduction/owner. Do not tick V0
if unexplained warnings remain.

## Official headless (3 loops)

```
$godot = Join-Path $env:LOCALAPPDATA 'HHGodotAgent/tooling/godot-4.7.1-stable/bin/Godot_v4.7.1-stable_win64_console.exe'
& $godot --headless --verbose --path godot/dogfood/superfighters --script res://tests/run_all.gd
```

| Run | EXIT | leftover Godot | leak phrases | stderr bytes |
|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 |
| 3 | 0 | 0 | 0 | 0 |

Banners (all three identical):

```
HH_VF_PATH title→fight→win/lose→restart
HH_VF LOOP=proven COMBAT=proven MAPS=proven NO_ERRORS=proven
HH_VF_HYGIENE sessions=20 muted=1 music=off status=proven
PASS: Vault Fighters first playable
```

Normalized banner SHA-256 (UTF-8, HH_/PASS lines):
`b53758c77339499ecfdc9ef524e41a3372fda11a6709214423dca59f901934d4`

Headless stderr SHA-256 (empty):
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

## Windowed play audio (20 create/clear)

```
$env:HH_VF_EVIDENCE_DIR = (Resolve-Path godot/dogfood/superfighters/.evidence/VF0WP2-20260829-ASIA-SAIGON-01)
& $godot --verbose --path godot/dogfood/superfighters --script res://tests/run_window_hygiene.gd
```

- EXIT 0, leftover Godot 0
- `HH_VF_WINDOW pid=35660 display=Windows size=(1280, 720) audio_driver=WASAPI`
- `HH_VF_HYGIENE_WINDOW sessions=20 music=on sfx=on`
- `PASS: Vault Fighters window hygiene`
- No `Leaked instance` / `Resource still in use` / `ObjectDB instances were leaked`

Host stderr (not ObjectDB): Vulkan loader cannot open Epic EOS overlay JSON
(`EOSOverlayVkLayer-Win64.json`) plus a registry layer-manifest warning.
This appears only on the windowed Vulkan path on this machine. Official
headless stderr is empty. Documented, not swallowed.

## What changed vs freeze leak

Frozen HEAD `0948224` played SFX in tests then quit: WARNING 31 ObjectDB +
ERROR 5 resources still in use.

VF0-WP2:

- `test_driven` mutes `SfxBank`: no `AudioStreamPlayer` allocation, no stream
  load/play; `last_id` still records. Headless/official tests stay muted.
- Normal play (`test_driven=false`) still starts looped fight music and SFX
  (window postcondition: WASAPI `music=on` `sfx=on`).
- `shutdown()` stops players, clears streams, restores Music bus, drops
  Arena node pins, frees transient VFX without `SceneTreeTimer`.
- Session nodes still `queue_free()` (immediate `free()` of physics bodies
  broke melee/floors in iteration 1).
- Fight music loop is import `edit/loop_mode=1`, not a runtime mutate of the
  cached `AudioStreamWAV`.

## Gaps (none blocking hygiene)

- Windowed `--verbose` host Vulkan/EOS overlay messages (see above).
- Hygiene is not Y8 parity and does not tick V0.
- Parent 20-8 unchanged: R9-WP4 `[ ]`, 59/60, G6 `[ ]`.

## Repro

Product files under `godot/dogfood/superfighters/` as hashed in `hashes.txt`.
Local logs/screens: `godot/dogfood/superfighters/.evidence/VF0WP2-20260829-ASIA-SAIGON-01/`
(`.gitignore`). Kill leftover Godot; one `--path` at a time.
