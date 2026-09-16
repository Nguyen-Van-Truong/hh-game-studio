# S53 journal v4 focused evidence

Candidate implementation only. No acceptance signature and no actual editor,
Linux validator, or public authentication claim comes from these tests.

- Native Windows suite: **5/5 passed**, 134.805 seconds, zero skips.
- Actual target PID 27444 and wrapper PID 24000 exited 0; bounded owned process
  tree verified clean. See `journal-v4-host.json` and `capture.json`.
- All source hashes recorded before the native run still matched afterward.
  `invocation.json` names journal, reducer, codec, native host/protocol, and
  test dependencies. This is a focused dependency map, not the coordinator's
  full final publication source closure.
- Pure reducer suite separately ran **12/12 passed** in 8.715 seconds via
  `python -B studio/tests/godot/test_publication_state_v4.py`; its console result
  was observed by the implementation worker. It is not part of the native
  runner's five-test count or a replacement for frozen coordinator reruns.

The native cases exercise real 12-object bundle staging, selector CAS, exact
durable canonical response storage, both save and replacement schema routes,
and readonly reopen. They also reject an incorrect script before native stage,
retain the original selector after failed retirement plus durable Stop, and
hold after a real selector CAS whose return is lost before durable SELECTED.
Synthetic engine/authority facts are labeled in the test source.

The five-test run used these new runtime bytes:

```text
publication_state_v4.py   23664a9905ad640fa28b1ed3c4de477db1108651093609152d9673a8ac75df4c
publication_journal_v4.py 77efa49c985be74b92c05ca9b343e705f2c08f34eea26b28355939ae3ad85a81
```

The reducer keeps the original UNKNOWN response across a subsequent Stop.
Receipt hashes exclude the response; the canonical response includes the
receipt hash and is itself persisted in the terminal event. V3 history replay
is unchanged and does not accept v4 events. No recovered writable owner or
unwitnessed selector reconciliation is implemented in this slice.
