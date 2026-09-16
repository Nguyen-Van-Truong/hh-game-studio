# S48 Linux execution boundary audit

AUTHORITY=0
AUDIT_SCOPE=read-only frozen source and existing evidence
AUDITED_AT=2026-09-17T00:13:00+07:00
FORMAL_GT03_ACCEPTANCE=false
PUBLIC_ACK=false
SANDBOX_ACCEPTANCE=false

S48 demonstrates bounded diagnostic execution and owned cleanup while the host
runner remains present. It does not establish a complete sandbox for autonomous
untrusted workloads. No Docker command, engine run, source/plan modification or
acceptance tick was performed for this audit. Only this report was written.

## Evidence identity and observed result

Both frozen manifests contain 74 source files. Recomputed hashes match every
listed file, and all case artifacts referenced by both captures match their
recorded hashes. This checks local byte consistency, not protected custody
against a concurrent same-user host attacker.

| Package | Frozen closure SHA256 | Capture SHA256 | Scoped observations |
| --- | --- | --- | --- |
| [Linux01](20260917-gt03-s48-linux-01/capture.json) | `f07f818f092bbb57b4d810e10eda2d3ac0ba126022786e250b8d4d905946c386` | `480cc182063d6fb6fc40295b5e1a94c3a69b781835343d574b47da6d6c1f3abb` | 8/9 fixtures; 9/9 lifecycle observations |
| [Linux02](20260917-gt03-s48-linux-02/capture.json) | `096239b1035bfcce0cb4cecf3251392d837cdaea66800428d920a7f4a5c462a5` | `13be617d1a9642f9492d0c8500c674a4ac30e48b519dd7a1dc43f93c69cf05f3` | 11/11 fixtures; 11/11 lifecycle observations |

Both use executor SHA256
`1e8cdb213f556c8521eb577acd51099d8d7ea2f09c57f8fff67c47f4e2e28fbb`
and validator lock SHA256
`2cfb076917b162cb053e98eefc7c97632b6970acb782a892c64a2c91cf134614`.
Linux02 fixture/runner hashes are respectively
`7ca8c6bbab336e83c3ee3cfc982700de44afa9f5bfd3e6433ed9de6e501fe383`
and `138c6d29469b48edfefe7d697dc8d73414d8787a2f600991556567e452cacfce`.
The source manifests preserve Linux01's different fixture/runner identities;
the newer observations must not be attributed to its older closure.

Linux01's three-second busy-tool run stopped before the callback marker.
Linux02's ten-second run observed the callback, then timed out and recorded
native exit 137, PID zero and owned removal. Its parse-static callback and
parse-static busy cases also observed execution, including native exit 137
and owned removal for the latter. Thus `--check-only` is not a promise that
submitted GDScript cannot execute. Forged success output did not enable
`public_ack`, `sandbox_acceptance` or `validation_attribution_proven`.

## Material resource configuration

The [frozen executor](20260917-gt03-s48-linux-02/source/studio/godot-addon/linux_executor.py)
lines 254–313 constructs and checks read-only root, two read-only private binds,
UID/GID 65532, dropped capabilities, no-new-privileges, built-in seccomp,
private IPC/cgroup namespaces, network none, no restart and logging driver none.
[Linux02 created inspect](20260917-gt03-s48-linux-02/valid_parse/created-inspect-stdout.txt)
SHA256 `abd0208cdd541295c41e4f610fe25549ea36c6a7db08cdacc0449c3a59f1f93e`
records the configured limits below.

| Surface | Configured bound | Evidence limit |
| --- | --- | --- |
| `/project/.godot` | 64 MiB, 8192 inodes | No exhaustion case |
| `/tmp`, `/home/validator` | 16 MiB, 2048 inodes each | Only `/tmp` byte-fill case |
| `/run` | 4 MiB, 512 inodes | No exhaustion case |
| `/dev/shm` | 16 MiB | No explicit inode option or exhaustion case |
| Cgroup memory/swap | 1 GiB / zero container swap | No OOM/peak-accounting fixture |
| Cgroup CPU/tasks | One CPU quota / 64 tasks | No fork/thread-limit fixture |
| Rlimits | CPU 10 seconds per process; file 8 MiB; core 0; descriptors 256; POSIX queues 8192 bytes | Not an aggregate lifetime or host-disk budget |
| Host retained stdout/stderr | 262144 bytes per stream | Actual flood retained exactly 262144 stdout bytes |

The earlier trusted [startup mount/cgroup record](20260916-gt03-s48-linux-startup/run-02/startup-stdout.txt)
SHA256 `95c2db2c9b144056d40d5cfebf378afa2dbaab4d3f723a90a5b5af6b38416b0e`
observes those cgroup values and runtime mounts on this backend. It belongs to
the trusted startup harness, which had an additional read-only harness bind;
it is not an in-container resource measurement for every later hostile case.

The four explicit data tmpfs mounts total 100 MiB and 12800 declared inodes.
Startup also observed `/dev` as a 64 MiB tmpfs and `/dev/shm` as 16 MiB: 180 MiB
of nominal tmpfs byte ceilings across these distinct mounts. This sum is not
a bound on all kernel memory, Docker metadata, host evidence, or the WSL VM's
storage. Kernel documentation separates tmpfs byte and inode limits and notes
that System V shared memory uses an internal mount, rather than `/dev/shm`.
[Linux tmpfs documentation](https://docs.kernel.org/filesystems/tmpfs.html).

## Prioritized remaining gaps

1. **Aggregate admission and retained storage are unbounded across runs.**
   `run()` lines 323–341 checks only a module-local incomplete-CLI list, then
   allocates a fresh output directory and UUID. There is no process-shared
   admission lease, active-container count, aggregate memory/task budget or
   evidence-retention quota. Multiple callers or host processes can each
   allocate the per-container limits; sequential runs retain new host files.
   UUID ownership prevents cross-container cleanup mistakes but does not
   prevent this amplification. Add cross-process admission, explicit aggregate
   budgets and owned retention/reconciliation before exposing automatic work.

2. **The wall deadline depends on the host remaining alive.**
   Lines 392–434 stop the attach CLI, inspect, kill the owned container and
   finally remove it. The Windows Job owns the CLI, not Docker's container.
   Host death, daemon unavailability or an unresolvable cleanup failure can
   bypass that path. `restart=no` does not stop an already-running container;
   CPU quota limits bandwidth, and per-process CPU time does not terminate a
   sleeping workload. The caller's 1–20 seconds bounds the attach wait, not the
   entire create/start/inspect/cleanup sequence. Existing timeout fixtures
   prove host-present cleanup only. A separate trusted lifetime supervisor
   and durable exact-owner orphan reconciliation need hostile tests, including
   attempts to signal/suspend the supervisor. A proposed PID1 timeout wrapper
   is not yet implementation or evidence. [Kernel CPU and task controls](https://docs.kernel.org/admin-guide/cgroup-v2.html).

3. **Writable runtime and kernel-resource coverage is incomplete.**
   Startup records writable `/dev/pts`, `/dev/mqueue` and `/proc`, with selected
   `/proc` paths read-only or masked; `/sys` and cgroups are mounted read-only.
   `/dev` is root-owned mode 0755, so its writable mount flag alone does not
   imply that UID 65532 can create arbitrary files there. These special mounts
   are not ordinary unbounded host-disk volumes, and no host-write escape was
   observed. Nevertheless, the current fixtures do not measure accessible
   PTY/queue/System-V/POSIX shared-memory objects, inode exhaustion, memory/task
   limits or cleanup of descendants. The queue rlimit does not substitute for
   that matrix. Test relevant operations and counters under the exact pin,
   reduce unneeded surfaces where supported, and distinguish configured
   denial from observed denial. Cgroup memory limits can have transient
   overshoot; they are not a byte-exact whole-host allocation guarantee.
   [Kernel memory controller](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory).

4. **Retained output is capped; all output transport/storage is not measured.**
   Linux02's [flood host record](20260917-gt03-s48-linux-02/stdout_flood/engine-host.json)
   counted 566403 stdout bytes read while retaining 262144; Linux01 counted
   734380 with the same retained cap. Both overflowed, ended native 137 and
   removed their owned container. `_cli()` lines 150–237 caps retained buffers
   and stops the CLI after observing overflow; lines 397–400 then inspect and
   kill the still daemon-owned container. Pipe/Docker buffering high-water,
   daemon overhead and stop latency under resource pressure are unmeasured.
   Logging driver `none` disables container log retention; it does not assert
   zero daemon metadata or evidence storage. [Docker logging drivers](https://docs.docker.com/engine/logging/configure/).

5. **Current child observations need appropriately narrow attribution.**
   `/tmp` fill reports 15 completed files and a rejected write, without an
   independent statfs/cgroup counter. The network fixture tries `192.0.2.1:443`
   without a reachable positive control; failure alone cannot prove every
   network boundary. Created-inspect configuration and trusted startup's
   loopback-only interface record are separate supporting observations.
   Submitted output, source/output custody and publication authority remain
   distinct boundaries; source hashes do not protect mutable host paths.

S48 may be described as **11 selected Linux diagnostic fixtures observed with
bounded per-container settings and host-present owned cleanup**. It must not
be described as complete runtime sandbox acceptance, a trusted validation ACK,
host-death proof or formal GT03 acceptance. S49 can address the above gaps on
a fresh source closure after the S48 checkpoint.
