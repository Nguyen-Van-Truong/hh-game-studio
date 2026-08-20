# gs-player

Separate Play process (I3). Reads `--snapshot <manifest.json>`, verifies
every hash, simulates at 60Hz, renders with `gs-render2d`. The GPU atlas is
packed from snapshot PNGs listed in `asset-manifest.json` (`TextureId(0)` is
always a 1×1 opaque white quad; missing or corrupt PNGs stay untextured).

```
gs-player --snapshot <manifest.json> [--headless] [--no-render] [--frames N] [--control-port 0]
gs-player --project <dir> --out <dir> [--include-debug]
```

`--project` + `--out` packs a standalone Play folder (`pack_project`): player
exe, snapshot files, `run.bat`. `out` must not be inside the project (I7).
No editor bus. Export is unsigned (no `.pfx` / editor cert).

`--frames` / `--headless` / `--no-render` never open a window (tests).
`--frames` stays the M2-1 path and does not start a control server.

`--control-port 0` binds **127.0.0.1** (ephemeral), writes `player.json`
`{pid, port, token, play_id, started_at}`, and serves a **persistent**
NDJSON JSON-RPC connection (idle read timeout 120s, write timeout 5s).
The token is a secret (I8) — never logged.

The play process hosts Luau on a dedicated simulate thread (`ScriptHost` is
`!Send`). The editor may depend on this crate for `build_snapshot` /
`pack_project` / `verify_snapshot` and `ControlClient` only. Agents must
not connect here; they call `play.*` / `build.*` on the editor bus.

## Flags and environment

| Flag / env | Effect |
|---|---|
| `--headless` | No window. Offscreen GPU still attempted for `obs.screenshot` unless no-render. |
| `--no-render` | No GPU. Simulate, event trace, and `obs.world_dump` work. `obs.screenshot` → JSON-RPC error `app_code: no_gpu`. |
| `GS_GPU=none` | Same as `--no-render`. |
| `GS_GPU=warp` | **Accepted.** This crate does **not** select a wgpu WARP adapter (that would be `gs-render2d` work). Treated as no-render so CI without a GPU still runs. No 60fps claim. |
| `GS_GPU=auto` or unset | Try a real GPU for screenshots; failure → `no_gpu` (process stays up). |

Determinism (MASTER 6.2) is same-machine only: same machine + same build + same snapshot + same seed + same tape → same per-frame world dump; there is no cross-machine claim.
| `GS_TEST_HANG_MS=<ms>` | **Test-only.** Next `step()` uses this fake elapsed (no sleep). `>2000` → exit 13 `SCRIPT_HANG`. |
| `--frames N` | Standalone headless simulate; no control server. |
| `--control-port 0` | Bind 127.0.0.1 ephemeral + persistent control. |

## Watchdog and memory (MASTER 6.5)

- One simulate frame `>2000ms` → write `hang_dump.json` when a play dir exists, `exit_report.json`, exit **13** (`SCRIPT_HANG`).
- Observed RAM `>1GB` → warning log. `>2GB` → exit **14** (`OOM_GUARD`).
- `play.step_frames` is capped at **3600** per call.
- Tests inject fake elapsed (`ControlHandle::inject_test_hang_ms` / `GS_TEST_HANG_MS`) or an injected byte counter (`inject_memory_bytes`). They do **not** sleep 2s or allocate 2GB.

Windows RSS uses `K32GetProcessMemoryInfo` `WorkingSetSize` (can include shared pages). That is a best-effort stand-in, not a perfect private-bytes meter. The guard function is unit-tested; process tests inject the counter.

## GS-EC notes (M2-5)

| Code | Player coverage |
|---|---|
| GS-EC-27 | `exit_report.json` on stop / watchdog / OOM; panic hook writes a best-effort report. A hard crash (abort) is editor-side (banner + stale pid). |
| GS-EC-28 | Editor `play.start` while a player lives (`E_PLAYER_RUNNING`). Not this crate. |
| GS-EC-29 | 0 / 2+ cameras in `gs-runtime-core` (`NoActiveCamera` / smallest id + warning). |
| GS-EC-30 | `play.step_frames` auto-pauses, then steps (`wp_m2_2`). |
| GS-EC-31 | `--no-render` / `GS_GPU=none`: screenshot → `no_gpu`. |
| GS-EC-44 | Stale `player.json` + dead pid cleaned on start (`wp_m2_2`). |
| GS-EC-48 | CI without GPU: `--no-render` or `GS_GPU=none`. `GS_GPU=warp` is the documented alias and is treated as no-render here. |
