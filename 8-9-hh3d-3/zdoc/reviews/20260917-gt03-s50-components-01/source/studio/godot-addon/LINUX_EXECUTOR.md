# Internal Linux diagnostic executor

`linux_executor.py` uses the already installed, running Docker Desktop Linux
backend from a trusted Windows host. It is not a public command endpoint, a
trusted parser attestation, a production save transaction or an acceptance
runner. Public discovery remains disabled. Child output may be forged by the
submitted project, even when the engine exits 0 without visible errors.

```python
result = linux_executor.run(
    project: Path,
    mode="parse",             # "parse", "import", or "profile-validate"
    output=fresh_output_path,
    timeout_seconds=20,        # integer 1..20
)
```

The example illustrates the call signature; pass a `Path` value as `project`.
There is no caller-supplied argv, entrypoint, Docker context, image, mount list,
resource limit, environment or container name. Invalid preflight arguments or
input raise `ExecutorError` before any container exists. After creation is
attempted, failures return a diagnostic record and perform owned cleanup or
explicitly report why ownership/completion could not be established.
Host cancellation is different: `KeyboardInterrupt`/`SystemExit` propagate
after bounded cleanup and evidence attempts, with the dirty diagnostic record
attached as `executor_result` (or `cli_result` for the internal CLI helper).

## Exact input and pin

For the original hostile diagnostic modes, `REQUIRED_FILES` is exactly `project.godot`, `scenes/fixture.tscn` and
`scripts/fixture_actor.gd`. Scene bytes are capped at 1 MiB and script bytes at
16 KiB. Script syntax is not interpreted by this host module. The only input
directories are `scenes`, `scripts` and an optional empty `.godot`. Extra files,
cache contents, symlinks, Windows reparse points, hardlinks and a modified
`project.godot` are rejected. Paths and ancestor entries are checked before
reading; each bounded file read checks metadata again afterward.

Use the exported `PROJECT_TEMPLATE` verbatim as UTF-8:

```ini
config_version=5
[application]
config/name="HH GT03 Linux validator"
[rendering]
renderer/rendering_method="gl_compatibility"
[threading]
worker_pool/max_threads=4
```

A terminal LF is required. The worker pool is explicitly bounded because the
documented default uses available logical cores; CPU quota alone is not a
thread-count limit. This setting still needs actual pin-specific probe evidence.
[Godot ProjectSettings](https://docs.godotengine.org/en/4.6/classes/class_projectsettings.html#class-projectsettings-property-threading-worker-pool-max-threads).

The executor copies verified bytes to its new `output/snapshot`, creates only
an empty `.godot` mountpoint there, and records input hashes. The source and
snapshot are checked again before startup and after shutdown. It does not
change the caller's project. `output` must be a fresh directory beneath an
existing checked parent and must not overlap the input tree.

`validator-toolchain.lock.json` separately binds the existing Linux/amd64 Python
image, official Godot 4.7.2 Linux executable/archive/checksum-list hashes, source
commit, Docker context/endpoint and accepted Windows owned-runner dependency.
The module verifies the exact lock bytes and actual binary hash. It does not
edit `studio/toolchain.lock.json`, install dependencies or pull images.

For a frozen source copy, trusted host configuration may set
`HH_STUDIO_LINUX_GODOT` to the existing binary's full absolute path. The filename,
hash, link checks and sole-file tool-directory restriction still apply. The
variable is never an IPC request field and never authorizes script execution.
Without it, the installation is located below the module's `studio/.local/tooling`.

## Fixed commands and containment

The fixed image entrypoint is `/usr/local/bin/python3 -I -B` with an inline,
locked preflight. It verifies PID 1, UID 65532, the pinned `/usr/bin/timeout`
SHA256 and Yama `ptrace_scope` in `{1,2,3}`, then `exec`s GNU timeout 9.1 into
the same PID 1. Timeout launches the verified
`/tool/Godot_v4.7.2-stable_linux.x86_64` with these fixed arguments:

```text
parse:  --headless --path /project --log-file /tmp/engine.log --check-only --script res://scripts/fixture_actor.gd
import: --headless --editor --import --path /project --log-file /tmp/engine.log res://scenes/fixture.tscn
```

Import opens the fixed scene, which may reference the fixed script. Tool code
can therefore execute inside the container; parser success does not grant it
live-editor or publication authority.

Each unique UUID container uses a read-only root and exactly two read-only
private binds (`/tool` and the disposable `/project` snapshot), UID/GID 65532,
all capabilities dropped, no-new-privileges, built-in seccomp, private IPC and
cgroup namespaces, network `none`, no devices/socket/ports, no healthcheck or
restart, and `--pull=never`. The host checks the actual created configuration,
image, environment, mounts, system masks and limits before start.

| Resource | Fixed limit |
| --- | --- |
| `.godot` tmpfs | 64 MiB, 8192 inodes |
| `/tmp` and `/home/validator` tmpfs | 16 MiB and 2048 inodes each |
| `/run` tmpfs | 4 MiB, 512 inodes |
| `/dev/shm` | 16 MiB |
| Memory / swap | 1 GiB memory; memory-plus-swap also 1 GiB, prohibiting container swap |
| CPU / PIDs | One CPU quota; 64 PIDs; per-process CPU time 10 seconds |
| Regular file / core / descriptors / message queue | 8 MiB per file; no core dump; 256 descriptors; 8192-byte POSIX queue limit |
| Container supervisor | TERM after `max(1, timeout_seconds-1)` seconds, KILL one second later; configured total 2..20 seconds |
| Host attach wait | Caller-selected integer 1..20 seconds plus 2 seconds to observe the supervisor |
| Host stdout and stderr | 256 KiB each, then stop; `--log-driver none` |

Writable data tmpfs mounts are nodev/nosuid/noexec and owned by 65532 with mode
0700. HOME/XDG/TMP point into these mounts. Docker also supplies special runtime
mounts; their complete effective behavior still requires the hostile-fixture
and resource-exhaustion matrix. These settings are not a claim of zero host
metadata or whole-VM disk use. [Docker tmpfs](https://docs.docker.com/engine/storage/tmpfs/),
[resource limits](https://docs.docker.com/engine/containers/resource_constraints/),
[network none](https://docs.docker.com/engine/network/drivers/none/).

## Host streams and lifecycle

GNU timeout runs as PID 1, without Docker `--init` or `--foreground`. Linux
prevents child SIGSTOP/SIGKILL from stopping namespace PID 1 and kills the
namespace's other processes when PID 1 exits. Timeout's kill-after state does
not let later handled signals reset its final alarm. Configured deadlines are
subject to kernel scheduling latency, rather than real-time guarantees.
[Linux PID namespaces](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html),
[coreutils 9.1 source](https://github.com/coreutils/coreutils/blob/v9.1/src/timeout.c).

Docker's default seccomp alone does not establish parent-tracing denial on this
kernel. The bootstrap fails before starting the engine unless Yama restricts
ptrace. Scope 1 denies a child attaching to this ancestor, which has not granted
a ptracer exception; scopes 2 and 3 are stricter. The project cannot change the
read-only sysctl without the dropped capability. The trusted host administrator
and existing backend remain part of the trusted environment.
[Linux Yama](https://docs.kernel.org/admin-guide/LSM/Yama.html),
[Moby seccomp profile](https://github.com/moby/profiles/blob/main/seccomp/default.json).

Every executor uses the same Windows global named mutex for the fixed Docker
context. Acquisition waits at most one second, then records
`EXECUTOR_ADMISSION_BUSY`. It coordinates threads, processes and source copies.
The mutex is held through container cleanup or persistence of its ambiguity.
ReleaseMutex/CloseHandle failures retain the handle, mark the result uncertain
and block further runs in that module. A failed release while ownership is
retained also leaves a durable rejecting state. If release succeeded but handle
close failed, the old process must not overwrite the next owner's record;
its leaked handle remains held locally and its result stays uncertain.
An abandoned mutex is never itself a cleanup proof.
Cancellation during mutex creation/wait retains an ambiguous admission owner.
Cancellation while receiving a ReleaseMutex result sets ownership unknown;
that process must not overwrite the recovery record because another caller may
already own it. These unresolved native-result states block the module and are
not automatically retried.

The bounded recovery record is
`%LOCALAPPDATA%/HHGodotAgent/linux-executor/desktop-linux/owner.json`.
The executor flushes and atomically replaces it before create, then records the
full ID before start. After admission, a new owner checks the daemon endpoint,
reconciles the recorded name/label/image/ID, stops it if needed, observes PID zero
and removes it before starting another engine. A bounded inventory of the
reserved context label must then be empty. Unknown containers deny admission;
the label alone never authorizes deletion. The mutex is global but this record
is per Windows account: another account's orphan yields access denial or an
unknown-container denial, not permission to clean it.

A lost create reply with no observed ID/object remains ambiguous and blocks
later requests until the actual owned object can be reconciled. A missing
object does not prove a daemon request cannot complete later. This store is
crash recovery for a trusted account, not protected custody against a same-user
attacker. There is no automatic ambiguity waiver or broad prune.

Every Docker CLI process is gated into a Windows owned kill-on-close Job before
the CLI launches. Both streams are drained with byte limits. A read error or
missing EOF cannot become a clean result merely because the process exited 0.
Reader exceptions, EOF completion, timeout, cap overflow, process exit and
settled Job count are recorded. Incomplete pipe ownership is retained and
blocks further runs in that module instance.
Reader and cleanup cancellations are retained while the remaining Job/helper/
pipe cleanup proceeds; the first cancellation is then re-raised unchanged.
One pipe-close failure does not skip the other pipes. Ordinary exceptions still
return dirty diagnostic rows. A cancellation cannot supply clean command,
missing-container or removal proof.

The container is daemon-owned, not a child of the Windows CLI Job; its PID 1
deadline continues after the host process/Job dies. A lost
create reply is reconciled using the unique name, UUID label and exact image;
only its verified full ID is used for kill/wait/remove. Timeout/cap/failed attach
requires fresh inspect and owned termination, followed by actual stopped state
and PID zero before removal. A final inspect must report that exact ID missing.
Daemon loss or uncertain identity stays a recorded gap; no prune, broad stop,
foreign-container removal or assumed cleanup occurs.

Engine streams are `engine-stdout.txt` and `engine-stderr.txt`. The engine's
`/tmp/engine.log` is intentionally ephemeral; it is not claimed as a captured
artifact. State, CLI logs, create argv, file hashes and `result.json` are kept
on success and failure. `command_host` / `container_state` are aliases of
`commandhost` / `state`; all are supplied for the fixture runner. Additive fields
`admission`, `owner_record_retained` and `supervisor` describe admission/recovery
and the configured timer. Native timeout statuses such as 124 and 137 remain
diagnostic failures. `host_death_acceptance` stays false in the API; separate
focused probes record their scoped observations.

`diagnostic_process_clean` requires the observed command/engine exit and clean
stream completion, no warning/error pattern, no OOM, input/snapshot/binary
integrity and verified owned removal. It never means that a submitted script
is benign, that its own output proves anything, or that parser/import semantics
are complete. `public_ack` and `sandbox_acceptance` are always false.

The host performs useful no-link/hash checks but does **not** claim protected
source paths or custody against a concurrent same-user host attacker. There
is no protected output importer, durable publication command journal, source
attestation, save/publication integration, or persistent recovery service here.
Those boundaries remain separate from the diagnostic executor.

Admission bounds simultaneous containers created by this executor, not other
Docker users or the whole daemon. Input snapshots are prepared before admission;
retained evidence has no aggregate storage quota. IPC/PTY/inode/shared-memory,
OOM and task-exhaustion coverage remains incomplete. Full sandbox acceptance
is therefore still false.

## Verification scope

`studio/tests/godot/test_linux_executor.py` performs pure rejection and mocked
lifecycle checks: unsafe inputs/configurations, immutable command shapes, lock
drift, lost create reply, capped output cleanup and stream-read failure. It
does not start Docker or Godot. The coordinator's actual Linux fixture runner
owns pin-specific parse/import, hostile-input, resource-limit and teardown
evidence; source presence and pure tests do not establish those runtime claims.

## Complete eligible profile

`profile-validate` is a separate fixed input path with eleven files. The trusted
factory pins config/addon/UID bytes and qualifies a closed scene/script grammar
before creating any container. The entire bundle is read-only; a third fixed
read-only `/harness` mount holds the separately pinned validation bootstrap.
Parse, import and fresh instance readback share the same container, cache and
PID1 deadline. No caller argument selects the harness or phase commands.
See `FIXTURE_PROFILE.md` for scope and attribution limits. Public ACK and full
sandbox acceptance remain false even after a matching native observation.

CLI Jobs now use addon-owned `cli_job.py`, including checked creation, queries,
termination and close. Constructor/close uncertainty retains cleanup ownership;
new CLI creation is blocked while a native owner is held. A failed helper kill
or wait does not skip Job cleanup or evidence finalization. Never-started stream
readers are distinguished from readers that failed to stop. The same strict
host-completion checks are used for command success, missing-container evidence
and owned removal, including actual zero-active and successful Job close.
Constructors are registered before native allocation, and exact process-object
lookup covers interrupted ownership handoff. A native allocation/close whose
result is hidden by cancellation remains held; an uncertain close handle is
never queried or blindly closed again. This ambiguity requires process restart.
See `CLI_JOB.md` for the scoped cancellation boundary and retry semantics.
