# GT-04 private absolute deadline seam — focused test review

Reviewed 2026-09-17 07:22 Asia/Saigon against coordinator-ready source. This is
component test evidence, not GT-04 acceptance or a frozen-closure critic verdict.

Only `studio/tests/blender/test_absolute_deadline.py` and this review were written
by this worker. Production, plans and Git were not mutated. No Blender/Godot,
native registry, writer session or journal was opened.

The focused command completed with actual process exit **0**:

```text
python -B -m unittest discover -s 8-9-hh3d-3/studio/tests/blender -p test_absolute_deadline.py -v
Ran 29 tests in 0.011s
OK
```

The tests exercise the real queue and IPC dispatch with in-memory clocks and
dispatch doubles, plus host submit/execute with project/transport doubles:

- Reject malformed integers, booleans, explicit wire null, out-of-range values,
  unexpected envelope fields and an absolute deadline embedded in the native
  command schema before any simulated effect.
- Reject a newly expired command before creating a queue receipt; expire queued
  work at the original absolute boundary; retain the shorter TTL bound.
- Wall-clock forward jumps cannot escape the absolute bound; rollback cannot
  extend the monotonic admission bound. A boundary crossed during lease checking
  is rechecked before dispatch.
- Exact-ID pending/completed/expired receipts remain detached from retry
  deadlines. Retries cannot renew or revive admitted work; changed command
  payloads still conflict. A command just before the boundary dispatches once.
- Stop drains both legacy and absolute-deadline tuples and preserves cancelled
  receipts. Monotonic expiry and writer-fence precedence remain fail-closed;
  inspect's lease exemption does not exempt its command deadline.
- Host submit and execute forward the caller's exact safe integer without
  substituting TTL or poll timeout. Absent deadlines preserve the legacy wire
  shape; execute polls results without resubmitting the command.

No defect was reproduced within this seam. The tests establish pre-dispatch
admission behavior only: they do not establish cancellation of a synchronous
native mutation already running, full public-ledger deadline binding, native
Blender process behavior or final GT-04 acceptance.

SHA-256 values observed immediately after the passing run:

| File under `8-9-hh3d-3/` | SHA-256 |
| --- | --- |
| `studio/blender-addon/ui_queue.py` | `1aa25aa0ed7f89bff4f8c111646d6318f6affea126c9c007cd8acd7199acf200` |
| `studio/blender-addon/ipc_client.py` | `c0db0dffe85c75e49f3ad1c04aa60f02c0d4f2f53ba6bcfe0e3ed029522eab43` |
| `studio/host/blender/ui_host.py` | `6b5e3e07411af88b93852b949661e041f6e37d2529e1bc0bf5481f4a7750ff30` |
| `studio/tests/blender/test_absolute_deadline.py` | `ff42766851ea9d853361cf887f522ecd4c89a901df20316910eb04ec227a54f3` |
