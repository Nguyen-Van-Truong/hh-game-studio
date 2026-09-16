# S48 existing Linux executor availability and trusted startup

AUTHORITY=0. SANDBOX_ACCEPTANCE=NOT_ESTABLISHED. GT03_ACCEPTANCE=NOT_ISSUED.

**A usable existing Docker Desktop Linux backend is present, and the pinned stock Linux Godot binary successfully starts under the proposed container restrictions.** No installation, pull, daemon setting, service start, Windows quota/mount, or existing container was changed. The initial read-only inventory scope was extended by the coordinator to the verified official archive under `studio/.local/tooling/` and a bounded trusted `--version` startup diagnostic. No submitted script/project code was executed. The accepted `studio/toolchain.lock.json` was not edited.

## Actual inventory, 2026-09-16

| Check | Observed result |
| --- | --- |
| `Get-Command wsl,docker,podman` | WSL at `C:\WINDOWS\system32\wsl.exe`; Docker at `C:\Program Files\Docker\Docker\resources\bin\docker.exe`. Podman was not found by this lookup or the two checked Program Files locations; no wider absence claim. |
| `wsl --list --verbose`, `wsl --status` | Only `docker-desktop`, already Running, WSL version 2; default version 2. No separate general-purpose Linux distribution was listed. |
| `docker version`, current context | Existing Docker Desktop 4.61.0 (219004), Engine/client 29.2.1, Linux/amd64 server, kernel `6.6.87.2-microsoft-standard-WSL2`, context `desktop-linux`. |
| Context endpoint | Local `npipe:////./pipe/dockerDesktopLinuxEngine`; no remote daemon selected. |
| `docker info` | cgroup v2 / `cgroupfs`; MemoryLimit, SwapLimit and PidsLimit true; built-in seccomp and cgroup namespace support reported; no warnings. Daemon default logging is `json-file`, so the probe explicitly overrides it with `none`. |
| Local candidate images | Existing Python 3.12 bookworm, Python 3.13 slim, Debian bookworm slim and Ubuntu 24.04 images. No Godot-tagged image was observed. No image was pulled. |

Status commands ran under separate owned Windows kill-on-close Jobs with 20-second command deadlines. Completed commands had actual exit 0 and settled active count 0. Two Go-template queries failed because requested fields were absent; they were corrected rather than interpreting the template errors as absent kernel support. No WSL shell or privileged distro was entered.

The selected public base `python:3.12-bookworm` already existed. Its exact image ID and RepoDigest are both `sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970` (repository prefix `python@` for the digest). It is Linux/amd64, declares no volumes or entrypoint, and carries only the expected public Python base environment keys. The launcher uses the immutable image ID and `--pull=never`. See `20260916-gt03-s48-linux-startup/run-02/image-selection.json` and the bounded original inspect output.

## Official Linux pin, verified before extraction/execution

The existing official checksum file's SHA-256 is `b8bdff6704f833e7a021df16ec08e1478edd5a285c1f894929b91a7f74a5c7c0`, matching the accepted lock. Its line 18 binds the Linux archive. The URL and expected SHA-512 were reported to the coordinator before download.

- [Official archive](https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip): 77,860,424 bytes.
- Archive SHA-512: `9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b1467edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65`.
- Archive SHA-256: `cadd3204e728a35d3f13adb7fd0d7902636b79f6b95c40c265eb73b6c35329e4`.
- Extracted ELF SHA-256: `8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e`; 146,414,384 bytes.
- Local binary: `studio/.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64`.
- Source release commit remains `ed1daf0bf001b61586d9930840f2f1394092c079`; actual version output was `4.7.2.stable.official.ed1daf0bf`.

Extraction required the verified archive checksum, exactly one expected filename, no symlink entry, ELF magic and a 240 MiB expanded-size cap. No archive entry was run during extraction. A copy of the locked [official checksum list](https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt) is retained in the startup evidence directory. A future Linux validator lock belongs in its separately leased addon scope; these artifacts do not change the accepted Windows pin.

## Actual owned startup result

Evidence: `20260916-gt03-s48-linux-startup/run-02/`. The exact Docker create argv is `create-argv.json`; every Docker invocation and limit is retained in its `*-host.json`. The trusted in-container script only hashes the binary, executes `--version`, and reads its identity, mount table, limits, cgroups and interfaces.

| Control/readback | Actual run-02 observation |
| --- | --- |
| Root and inputs | Root filesystem read-only. Exactly tool, trusted harness and disposable project binds, all read-only. No Docker socket, user profile, device or writable host bind. `/etc/hosts`, hostname and resolver mounts also read-only. |
| Identity | UID/GID 65532; all five capability masks zero; `NoNewPrivs=1`; `Seccomp=2`. Private IPC/cgroup namespaces; network mode `none`; only interface `lo` observed. |
| Writable tmpfs | `/project/.godot` 64 MiB / 8192 inodes; `/tmp` 16 MiB / 2048; `/home/validator` 16 MiB / 2048; `/run` 4 MiB / 512. Each uses nodev/nosuid/noexec, owner 65532 and mode 0700. `/dev/shm` is separately capped at 16 MiB; runtime `/dev` reports 64 MiB tmpfs. |
| Process resources | `memory.max=1073741824`, `memory.swap.max=0`, `pids.max=64`, `cpu.max=100000 100000`. Per-process CPU 10 seconds, regular-file size 8 MiB, core dump zero, open files 256 and POSIX message queue 8192 bytes. |
| Host bounds | `docker start --attach` wall deadline 20 seconds; stdout and stderr each hard-capped at 262144 bytes in the broker; actual 6653/0 bytes. Docker log driver `none`; no restart/healthcheck. |
| Completion | Godot exit 0, exact pinned version, empty Godot stderr. Attached CLI exit 0; `docker wait` returned 0. Independent inspect: exited, Running=false, PID=0, ExitCode=0, OOMKilled=false. |
| Cleanup | Exact created ID `69f3e07b62acb71082c919bfd5f8c7761f3bd7a3690d05c7c98d39bb73310a58` and UUID owner label were rechecked; removal succeeded; subsequent inspect reported no such object. All recorded CLI Jobs settled to active count zero. Binary hash unchanged. |

Run-01 remains preserved: Godot/container exited 0, but the initial host helper sampled a Job active count of 1 immediately after CLI exit. It safely failed the diagnostic and still verified the exited container and removed its owned ID. Run-02 adds a bounded one-second Job-settle observation; it does not rewrite run-01 as a clean run.

## Helper handoff and exact reproduction

The frozen prototype is `20260916-gt03-s48-linux-startup/capture.py`; its SHA-256 is `aa7dc56319e9367fa0f281d1ce4da15bd62382e9373101ce891d836ffad9cace`. The trusted child observer is `harness/startup_inside.py`, SHA-256 `8cf2f884792e64ac2eeb5134b0349a507d80b3a72cb31ab15207ccfb41cc3e29`. Copies of both and the accepted owned-runner dependency are in run-02. `source.json` records those identities. `artifact-sha256.json` binds the evidence, configuration and this report separately from any product acceptance.

Prototype helper `cli(args, output, label, timeout=20, cap=262144)` gates each Docker CLI process into the existing owned Job before launching it, drains both streams with byte limits, records actual exit/timeout/counts, and verifies Job cleanup. It uses only `_job_for_process`, `_job_active_count`, `_terminate_job` and `_close_job` from `studio/build/bootstrap/run_fixture.py`, hash `ea522450acc46f90be5e2a7b9257e73ce8b619948105b2c9073aac1f881c7328`. The container itself is daemon-owned, so Windows Job cleanup is supplemented by ID/label-verified inspect/kill/wait/remove; killing the CLI alone is never container cleanup.

Reproduction from repository root, with a fresh output label:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt03-s48-linux-startup/capture.py run-03
```

This entry point intentionally supports only the trusted startup diagnostic. The coordinator owns any reusable validator/lease/queue integration under addon/tests. No addon source was written here.

## What this enables, and what remains unproved

Docker documents read-only roots, nonroot/capability controls, per-container logging and resource flags; these settings were also read back in this run. [Run reference](https://docs.docker.com/reference/cli/docker/container/run/). Linux tmpfs supports explicit size/inode caps, but can otherwise reach disk through swap; equal memory and memory-swap limits disable container swap. Actual cgroup readback was zero swap. [tmpfs](https://docs.docker.com/engine/storage/tmpfs/), [resource limits](https://docs.docker.com/engine/containers/resource_constraints/). Network `none` creates only a private loopback device; observing it is not yet a exercised denial matrix. [Network isolation](https://docs.docker.com/engine/network/drivers/none/).

This provides a concrete alternative to the unavailable Windows hard-disk provisioner. It establishes version startup and configured limits, **not complete import/parser confinement or a whole-host zero-disk-write guarantee**. Docker's shared backend still maintains bounded per-container metadata, and other existing workloads are outside this probe. No dependency was installed; full headless editor/import startup may still reveal lazy-loaded library or read-only-sidecar requirements.

Before submitted scripts: exercise the actual editor/import path with the complete pinned dependency closure; test tmpfs byte/inode exhaustion, file-size and output floods, memory/process/CPU/time limits, forbidden writes and network access against positive controls, and crash/cancel/daemon-loss cleanup. Audit every writable mount, special filesystem, inherited descriptor and daemon-produced artifact. Keep input immutable and import output untrusted; perform bounded verified extraction and publication through the separate Godot publisher. Neither this startup nor Docker availability closes the GT03 sandbox or publication acceptance gates.
