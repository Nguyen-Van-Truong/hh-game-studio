# VPS/OS conformance research — GT-01 → GT-10 (R13)

Date: 2026-09-13 (Asia/Saigon)  
Scope: read-only audit of `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt`.  
This report is research/evidence only; it does not change WP status and cannot be used as acceptance by itself.

## Executive result

The current plan already names the right controls (one process tree, Job Object/process group, short UTF-8 roots, Unicode/long-path tests, separate headless/windowed lanes, bounded Blender jobs, Android `SKIP_ENVIRONMENT`, and host preflight). The following sources confirm the platform semantics and add implementation details that should be explicit in the relevant WP checklists:

* Windows Job Objects manage descendants as a unit, can enforce limits, and `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` terminates associated processes. A child can escape only through an explicitly permitted breakaway path; therefore the runner must record breakaway policy and independently enumerate leftovers. [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
* Linux `setsid()` creates a new session/process group and `kill(-pgid, signal)` addresses a process group. cgroup v2 additionally exposes `cgroup.events` population state and (on supported kernels) `cgroup.kill`; availability and permissions vary, so process-group cleanup plus post-exit enumeration remains the portable baseline. [setsid(2)](https://man7.org/linux/man-pages/man2/setsid.2.html), [kill(1)](https://man7.org/linux/man-pages/man1/kill.1.html), [cgroup v2](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
* Godot `--headless` disables rendering/window management and is suitable for no-GPU CI; it cannot provide visual/focus evidence. Keep a distinct windowed lane. [Godot DisplayServer 4.7](https://docs.godotengine.org/en/4.7/classes/class_displayserver.html), [Godot feature list](https://docs.godotengine.org/en/4.7/about/list_of_features.html)
* Blender Python API access is not thread-safe. Keep all `bpy` mutations on Blender's main thread; parallelize only separate Blender processes with bounded count and per-process timeout/memory limits. [Blender Python threading gotchas](https://docs.blender.org/api/main/info_gotchas_threading.html)
* Windows long paths require both the system `LongPathsEnabled` setting and an application manifest `longPathAware`; relative paths remain subject to `MAX_PATH`. [Microsoft maximum path length](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation)
* Android Emulator acceleration must be detected, not assumed. Official tooling provides `-accel-check`; WHPX is recommended on current Windows, KVM on Linux, and unsupported nested virtualization/software rendering must be reported separately. An unsupported graphics mode can crash or produce incorrect images. [Android hardware acceleration](https://developer.android.com/studio/run/emulator-acceleration), [Emulator command line](https://developer.android.com/studio/run/emulator-commandline)

## Validation matrix

| ID / WP | Host preflight and test | Required observation/evidence | Failure classification |
|---|---|---|---|
| OS-01 / GT-01 | Record OS build, architecture, locale/encoding, filesystem, CPU/RAM/GPU, Godot/Blender hashes, display/audio mode. | Immutable JSON preflight bound to `run_id`, source hash and tool hashes; UTF-8 output parses. | Missing/unstable metadata = FAIL evidence, not PASS. |
| OS-02 / GT-01, GT-06 | Launch exactly one fixture process tree. Windows: assign root before resume, no breakaway, kill-on-close. Linux: `setsid`/dedicated process group; record PGID/session. | Host-captured exit code, timeout reason, descendants before/after; zero leftovers after grace period. | Any escaped/leftover process = FAIL and quarantine fixture root. |
| OS-03 / GT-01, GT-07 | Crash/timeout/Stop during Godot and Blender child launch. Exercise PID reuse and parent death. | Cleanup attempt, process-group/job query, second independent leftover scan; no kill by PID alone. | Unknown owner/PID reuse or cleanup uncertainty = FAIL/RECOVERY_REQUIRED. |
| OS-04 / GT-02, GT-03, GT-04 | Unicode (Vietnamese), spaces, reserved names, invalid UTF-8/JSON, traversal, UNC/ADS/reparse/symlink/hardlink, near-260 path. | Accepted safe paths round-trip; rejected paths include reason code; no raw host path/token in evidence. | Any path escape or undecodable log = FAIL. |
| OS-05 / GT-03, GT-06 | Godot `--headless` deterministic lane with fixed seed/trace. | State/hash/exit and warnings/errors; no visual claims. | Headless-only evidence cannot satisfy focus, screenshot or rendered UX rows. |
| OS-06 / GT-03, GT-06 | Windowed Godot lane on an interactive desktop/display server. | Input focus, menu/start/quit, screenshot/video, same frozen source hash as headless lane. | No display/session/focus = `SKIP_ENVIRONMENT` for visual lane, not PASS. |
| OS-07 / GT-04, GT-05 | Blender background export with no persistent `bpy` worker threads; bounded independent processes. | Real Blender exit, stdout/stderr warning scan, GLB hash and manifest. | Threaded `bpy`, timeout, OOM, warning/error = FAIL; retry only with new run id. |
| OS-08 / GT-08 | Android SDK/AVD/device preflight; run `emulator -accel-check`, capture ABI/API/GPU mode, cold boot/wipe state. | `adb` install/launch/exit, logcat, accelerator result, physical-device identity for hard gate. | Missing SDK/AVD/accelerator/device = `SKIP_ENVIRONMENT` plus remediation; emulator-only cannot replace physical-device proof. |
| OS-09 / GT-08, GT-09 | Linux VPS cgroup/process-group capability check and disk/RAM quotas. | cgroup path, controllers/permissions, free disk, OOM/timeout diagnostics. | No delegation permission or memory/disk budget = `SKIP_ENVIRONMENT`; do not silently run unrestricted. |
| OS-10 / GT-10 | Clean install/upgrade/rollback/uninstall on short and long roots, same-volume atomic replace and cross-volume refusal. | Manifest/hash/schema, independent installer exit, post-rollback readback and leftover scan. | Cross-volume/non-atomic replacement or stale manifest = FAIL. |

## Explicit SKIP_ENVIRONMENT rules

A skip is allowed only when the missing capability is environmental and the product contract remains untested. The runner must emit `status=SKIP_ENVIRONMENT`, `reason_code`, remediation, host preflight, source/tool hashes, and a reproducible command. A skip is never converted to PASS by a banner, caller-supplied JSON, or a zero exit from a wrapper.

* **Windowed Godot:** no desktop session, Wayland/X11/Windows display, focus, or usable GPU. Headless state tests may still run in their own lane.
* **Android:** SDK/AVD/image absent; `-accel-check` reports no usable WHPX/KVM/hypervisor; nested VM forbids acceleration; no supported physical device for the GT-08 hard gate; GPU mode falls back to software. Software/emulator results are diagnostic and must carry the exact mode.
* **Linux isolation:** cgroup delegation unavailable. A dedicated process group may be used for diagnostics only if the run is labelled non-acceptance and post-exit enumeration succeeds.
* **Windows paths:** host or tool is not long-path aware for the long-path case. Short-root cases can run; long-path row remains skipped with registry/manifest remediation.
* **Resource budget:** insufficient RAM/CPU/disk or VPS throttling prevents the declared bound. Do not increase limits silently; record observed limits and rerun on a declared profile.
* **Locale/encoding:** console cannot emit/parse UTF-8 safely. Use a UTF-8 file/pipe where possible; otherwise skip Unicode evidence and retain the raw failure only after redaction.

## Missing or under-specified safeguards to carry into WP checklists

1. **Job assignment timing:** require assigning the Windows Job Object before resuming the child, prohibit breakaway flags, and log the job limit/query result. `KILL_ON_JOB_CLOSE` alone is insufficient if assignment fails.
2. **Linux escalation path:** define TERM→grace→KILL for the process group, then (when permitted) cgroup kill, followed by independent `/proc`/command-line enumeration. Record PID, start time and cgroup/session to avoid PID-reuse mistakes.
3. **Capability preflight as data:** include `-accel-check`, display server, cgroup delegation and long-path awareness as structured fields rather than prose-only logs.
4. **Resource limits:** set per-run wall time, CPU, memory and disk budgets; classify OOM, host throttling and quota exhaustion distinctly from product failures.
5. **Two-lane evidence binding:** headless and windowed runs must share a frozen source hash and trace seed but retain separate acceptance rows; a window screenshot must never be inferred from a headless pass.
6. **Blender process hygiene:** enforce one writer per `.blend` path, no `bpy` from worker threads, and terminate all subprocesses on timeout before releasing the fixture lease.
7. **Android state isolation:** cold boot or wipe AVD, capture API/ABI/GPU/accelerator, and ensure `adb` exit/logcat are independently captured instead of trusting a test wrapper.
8. **VPS filesystem constraints:** check free space/inodes and same-volume atomic rename before destructive tests; do not use network/UNC mounts for official evidence.

## Decision against current plan

No sequencing change is required. These findings reinforce the existing `PORTABILITY_POLICY`, `ANDROID_POLICY`, single-process rule, source-hash binding, and `SKIP_ENVIRONMENT` language. They should be copied as concrete test rows when GT-01 evidence is reminted and when GT-08/GT-10 are implemented. This report does **not** authorize ticking GT-01 or opening GT-02.

