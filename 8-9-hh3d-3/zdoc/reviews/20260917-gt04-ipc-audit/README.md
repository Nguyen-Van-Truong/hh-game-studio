# GT04 owned Blender IPC candidate

AUTHORITY=0; PUBLIC_ACK=false; GT04_ACCEPTED=false.

Final package: `20260917-gt04-ipc-05`, source closure
`4f316a349d569230dab3c74e37c0af18eeabce998337f46a73c7bab5a9be8689`.
61 Python tests passed, including 21 new framing/routing/startup regressions;
20 native checks passed. The two ordinary Blender sessions and both outer
process lanes exited cleanly with checked zero-process Jobs. A third Blender
was observed through a retained process handle while its owning Python host
intentionally exited 73 without cleanup; the native process then terminated.
No Blender process remained after the run.

`BlenderUIHost` in `studio/host/blender/ui_host.py` exposes `submit`, `result`,
`execute`, `stop`, and `close`. It opens only its fresh, private factory scene.
A bounded one-shot inherited stdin pipe transports the random session key
after checked Job assignment; the key is absent from argv and environment.
Two loopback channels use HMAC over canonical JSON, binding session, direction,
channel and sequence. Each frame/buffer is at most 64 KiB plus its length field;
messages and queue entries are bounded. Control reserves room for Stop and quit.
Blender polls nonblocking sockets on one main-thread timer, reads control first,
and only then executes a queued bpy operation. `UIAdapter(external_poll=True)`
suppresses its own timer; the default UI behavior remains unchanged.

The native fixture exercised create, original receipt replay, native Undo/Redo,
transform readback, stale revision/no effect, fixed-slot save, Stop and retained
lookup, orderly close, broken-channel close, and actual host-process death.
Handshake evidence reports one Python thread in each Blender process. Host log
drains/watchdog threads run outside Blender. Unit fault injection fails the
first and second log thread starts while the subprocess gate remains closed;
both cases release the checked Job without launching the fake test executable.

Remaining GT04 work includes durable journal/recovery and writer lease/fencing,
production .blend admission and resource limits, export integration and independent
review. Stop is serviced between main-thread operations; it cannot interrupt a
currently executing bpy operator. A lost reply means an uncertain effect, not a
public commit. The save result remains `durable_publication=false`; this work
does not prove general hostile-writer atomic replacement. The IPC save proof
checks saved bytes; previous native UI save/reopen evidence remains separately
versioned and is not relabeled as this source.

Preserved diagnostics: IPC01 incorrectly assumed exactly two live Job members;
IPC02 held its parent directory without WRITE sharing, so Blender could create
its `.blend@` staging file but could not rename it. The final host reuses
`SafeCreateApi.open_parent(publish=True)`: READ|WRITE sharing, DELETE denied,
root identity retained, private ACL checked before dispatch. IPC03/04 are earlier
passing snapshots. Never assign their results to IPC05. These findings reuse the
S43 Windows sharing lesson rather than modifying GT02 primitives.

Reproduce a fresh native package:

```powershell
python -B 8-9-hh3d-3/studio/tests/blender/run_blender_ipc_probe.py --output 8-9-hh3d-3/zdoc/reviews/NEW_UNIQUE_GT04_DIRECTORY
```

Read-only artifact verification:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-ipc-audit/verify_evidence.py
```

`portable-artifacts.json` excludes generated user/temp/recovery/cache directories
and raw private staging leftovers. The final saved fixture is included and hashed.
This is historical trusted-host observation, not formal acceptance or a new live
OS isolation test. The earlier UI runner's hardcoded 40-test count belongs to its
old frozen capture; the new IPC runner executes and records all 61 current tests.

Primary references used: Blender documents that persistent Python threads are
[unsupported](https://docs.blender.org/api/main/info_gotchas_threading.html);
Python documents inherited subprocess
[stdin and Windows process handles](https://docs.python.org/3/library/subprocess.html).
