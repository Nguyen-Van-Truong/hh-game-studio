# Clean-room Y8 measurement rig

`y8rig.py` opens a configured game URL in a headed, persistent Chromium profile and records ordinary keyboard/mouse actions plus the browser's CDP `Page.startScreencast` frames. It does not read the page, DOM, canvas, network, runtime, debugger, or game files. The query string in `url` is passed to `page.goto` unchanged.

The rig is deliberately run only through the project guard. From the product root, a bounded invocation looks like this (the parent agent chooses the run id and evidence path):

```powershell
python tools/run_guarded.py --project-root . --timeout 300 --command-id cmd.sa02.y8rig.1 --source tools/y8rig/y8rig.py -- `
  python tools/y8rig/y8rig.py --project-root . --scenario tools/y8rig/scenarios/sample.json --output .local/y8rig-captures/sa02-run-01
```

Set `PLAYWRIGHT_BROWSERS_PATH` to the installed `.local/tooling/playwright-browsers`
directory before running. The optional guard `--evidence` argument is a JSON
**file** path, not the rig's `--output` capture directory. Omit it to use the
automatic `.local/runs/<run_id>/manifest.json`, or choose a distinct `.json`
path. Passing a capture directory causes a manifest rename error after the
child exits; preserve and inspect the existing run/capture instead of rerunning
solely to replace it. `--source` is relative to the product root, not its parent
worktree.

The runner refuses to start when `.local/run_guarded.lock` is absent. `run_guarded.py` is the owner of the machine measurement lock (`%LOCALAPPDATA%\HHGodotAgent\measure-window.lock`), scheduled `HHStudio.*` monitoring, the project lease, timeout, and child cleanup. Do not launch this runner directly or run another browser/test worker against the same product path.

The scenario format is described by [`scenario.schema.json`](scenario.schema.json). Actions are `wait`, `click`, `key_down`, `key_up`, and `hold`. A key held when a later action fails is released in `finally`; the action log stores UTC and monotonic start/finish times. `focus_click` defaults to a center click at `(640, 360)` before recording.

Each run writes `run.json`, `actions.json`, `frames.json`, and `frames/frame-######.png` below the requested output directory. `frames.json` contains the CDP metadata timestamp for every frame and observed cadence (`frames`, elapsed seconds, min/max/mean intervals, and FPS). The output is local evidence; it is not committed. Frame timestamps are browser-provided and the receive monotonic time is recorded for audit.

For a local self-check, copy `scenarios/fixture.json`, replace its `file:///ABSOLUTE/...` URL with the absolute path to [`fixture/keyboard.html`](fixture/keyboard.html), and run it through the same guard. The included page is a neutral page authored for this rig. [`fixtures/neutral.png`](fixtures/neutral.png) is a static neutral image for checking file handling; it is not a reference capture.

The parent setup owns the Playwright Python environment and Chromium installation under `.local`; this directory intentionally contains no installer, browser binary, or downloaded reference capture.
