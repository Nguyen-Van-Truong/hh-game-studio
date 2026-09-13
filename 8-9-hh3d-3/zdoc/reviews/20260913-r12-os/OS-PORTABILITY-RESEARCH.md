# OS/VPS portability research for GT-01–GT-10

## Evidence-backed findings

- **Godot CI/headless:** Godot documents `--headless` for environments without GPU access, and supports command-line export including Android. Headless disables rendering/window management, so visual assertions must run in a separate windowed lane; do not treat headless as screenshot evidence. See [Godot command-line tutorial](https://docs.godotengine.org/en/latest/tutorials/editor/command_line_tutorial.html) and [RenderingServer headless behavior](https://docs.godotengine.org/en/stable/classes/class_renderingserver.html).
- **Process-tree cleanup on Windows:** Windows Job Objects manage a process group, enforce CPU/memory/time limits, and can terminate all children atomically. Use a job object for Godot/Blender descendants where available; still record whether a child escaped via breakaway and verify no leftovers after exit. See [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
- **Windows paths:** Win32 historically limits paths to `MAX_PATH` (260); long-path behavior requires both the system setting and an application manifest declaration. Keep workspace/evidence roots short, test Unicode and long paths, and fail with a clear diagnostic when the host is not long-path aware. See [Maximum Path Length Limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation).
- **Blender concurrency:** Blender’s Python API is not thread-safe; background threads can crash. Use one Blender process per fixture and prefer multiprocessing for independent jobs. If a thread is used only for non-`bpy` work, join it before Blender exits. See [Python Threads are Not Supported](https://docs.blender.org/api/main/info_gotchas_threading.html).
- **Blender batch mode:** Blender documents `--background` for non-UI operation. Treat stdout/stderr and the real process exit as acceptance inputs; do not rely on a generated report or caller-supplied exit integer. See [Blender command-line arguments](https://docs.blender.org/manual/en/5.1/advanced/command_line/arguments.html).
- **Android CI/emulators:** Android’s official CLI supports creating/starting/stopping AVDs and `adb`-driven instrumented tests. Emulator acceleration (KVM/HAXM) may be unavailable on VPS; provide a software-rendered fallback and classify it separately from accelerated runs. Use cold-boot/wipe-data options to avoid state leakage between runs. See [Start the emulator from the command line](https://developer.android.com/studio/run/emulator-commandline), [Command-line tests](https://developer.android.com/studio/test/command-line), and [Manage virtual devices](https://developer.android.com/studio/run/managing-avds).

## Concrete mitigations to add to implementation/checklists

1. Add a host preflight record: OS/version, architecture, Godot/Blender hashes, locale/encoding, filesystem type, available RAM/CPU, GPU/headless mode, and Android acceleration status.
2. Run exactly one official Godot/Blender process per product path. On Windows attach child processes to a Job Object; on Linux use a dedicated process group/session and kill the group on timeout, then independently enumerate leftovers.
3. Exercise path cases in tests: Vietnamese/Unicode names, spaces, near-260-character Windows paths, symlink/reparse/hardlink rejection, UNC/ADS rejection, and atomic replace across same volume. Keep default CI roots short.
4. For Blender, serialize all `bpy` access in the main process; parallelize only separate Blender processes with bounded worker count and per-process memory/time limits.
5. Keep Godot headless and windowed evidence as distinct lanes. Headless verifies deterministic state/exit; windowed verifies input/focus/rendered UX. Require matching source hash and run metadata before comparison.
6. Android lane should detect missing SDK/AVD/accelerator, emit `SKIP_ENVIRONMENT` with remediation, and never downgrade a skipped emulator to PASS. Reset AVD state between runs and capture `adb`/emulator exits independently.
7. Normalize logs to UTF-8 with replacement-resistant error handling; redact host paths/tokens before evidence commit. Avoid printing raw Unicode paths through legacy Windows console encodings.

## Limits and uncertainty

The sources document platform behavior and supported commands; they do not prove that any particular VPS image, hypervisor, GPU driver, or filesystem is configured correctly. VPS variability must be covered by preflight and a matrix of observed runs. Claims about third-party MCP reliability, benchmark counts, or star/tool totals require direct reproducible tests and are not evidence here.

## Recommendation for the current plan

Keep the existing strict single-process, source-hash, postcondition, rollback, and critic gates. Add the mitigations above as validation requirements/fixture cases; do not make an external MCP repository or an “open lane” the core runtime. Retain `OPEN_LANE_POLICY=DISABLED_BY_DEFAULT` unless a later isolated-lane ADR proves process, network, secret, and license isolation.
