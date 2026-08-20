# workers/imagegen

Thin Python 3 watcher for the imagegen job queue (MASTER 8.2 / T6.1).
**I9-legal:** stdlib only; writes staging only; no new language/framework.

## Providers (GATE G3 = B+C)

- **B (official prerequisite):** local ComfyUI. This watcher *probes*
  `GS_COMFY_URL` (default `http://127.0.0.1:8188`). It does **not** generate
  images and must not be described as a working ComfyUI integration.
- **C (optional):** remote HTTP API. Config lives **outside** the project:
  `%APPDATA%/hh-game-studio/imagegen.json` (Windows) or
  `$HOME/.config/hh-game-studio/imagegen.json`. The watcher never reads that
  file (no API key in this process). `gs doctor` reports key present/absent.
- **Stub (tests only):** `GS_IMAGEGEN_STUB=1` writes a 1×1 PNG +
  `result.json` `{ok:true, provider:"stub"}`. That is a fixture, **not** a
  real provider result.

## Writes (GS-EC-55)

Only:

```
<project>/.gs/staging/jobs/<job_id>/out.png
<project>/.gs/staging/jobs/<job_id>/result.json
```

`dest_rel_hint` is not a write path. Never write `assets/`. Never open
`.gs/runtime/endpoint.json`.

Claim / heartbeat / finish: `gs-cli jobs-claim|jobs-heartbeat|jobs-finish`
(Rust `gs-jobs`). Cancel = `.gs/jobs/cancel/<job_id>.marker`.

## Run

```
cargo build -p gs-cli
set GS_ROOT=D:\path\to\project
set GS_CLI=D:\path\to\hh-game-studio\target\debug\gs-cli.exe
python workers\imagegen\watch.py
```

Or: `cargo run -p gs-cli -- doctor` (exit ≠ 0 until Python + ComfyUI or a C key).

`requirements.txt` is empty on purpose (stdlib only).
