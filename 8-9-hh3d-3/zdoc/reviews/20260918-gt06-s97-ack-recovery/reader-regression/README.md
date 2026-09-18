# S97 actual native reader regression fixture

Prepared for coordinator execution; creating these files did not launch a test
or engine. The candidate reader is pinned to
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`.
This is supplemental reader behavior evidence. It is neither a full native
benchmark nor formal acceptance, and it does not establish the exact S96 cause.

Run one invocation at a time under the coordinator's outer owned capture. From
`8-9-hh3d-3`, the first normal START case is:

```powershell
python -B zdoc/reviews/20260918-gt06-s97-ack-recovery/reader-regression/run_reader_regression.py --run-id gt06-s97-reader-start-normal-01 --stage start --case normal
```

Use `--stage ack` for the same ACK case, with a fresh run ID. Each invocation
creates only `reader-regression/runs/<run-id>/`, rejects reuse, freezes the
actual imported source dependencies and helper/project bytes, verifies the
pinned Godot 4.7.2 executable, and runs an inactive import before one real GUI
editor. Each process has its own checked Job owner and a 30-second stage wall
watchdog. The outer capture must retain the orchestrator's actual exit and
cleanup separately; `result.json` explicitly says that exit is not yet observed.

The fixture inherits the candidate's START/ACK readers, shared open helper,
normal `_process` heartbeat/deadline dispatch, receipt validation, and failure
path. It uses the accepted fixture factory, real editor adapter, edited root,
semantic snapshot, file hashes and FileAccess. It initializes a reader slot
directly and intercepts the successful advance after the original receipt is
recorded, before any native cycle. Startup/boot, the command producer, complete
batch execution and whole-campaign memory behavior are outside this fixture.

Run each row for START and ACK. Case names are fixed choices; arbitrary scripts,
file paths, timeouts and output locations are not CLI inputs.

| Case | Actual fixture | Required outcome |
| --- | --- | --- |
| `normal` | Valid receipt, accepted close/fsync/rename/readback publisher | Exactly one original receipt and one advance, native/helper exit 0 |
| `read_overlap` | Valid bytes with a real read handle held throughout reader execution | Same success without an open failure |
| `locked_release` | Real DELETE-access handle with share read/write/delete; release 750 ms after retained native first-open-failure artifact | Multiple normal frames, one pending and one recovered diagnostic, exactly one validated receipt/advance |
| `locked_timeout` | Same real handle held until native exit | Original reader rejects at its unchanged absolute slot deadline, no receipt/advance, actual native/helper exit 86 |
| `malformed` | Published `{` bytes | Immediate JSON rejection on first successful open |
| `locked_malformed` | Same malformed bytes, real sharing denial then release | Open recovery followed by immediate JSON rejection, no receipt/advance |
| `wrong_hash` | Valid JSON with a mismatched ready/native-batch hash | Immediate HASH rejection |
| `wrong_schema` | Valid JSON with schema version `9.9.9` | Immediate BINDING rejection |
| `empty` | Zero-byte published file | Immediate SIZE rejection |
| `oversized` | 8,193-byte published file | Immediate SIZE rejection |
| `short_read` | Explicit disposable-copy buffer-shortening fault | Immediate distinct SHORT_READ rejection |
| `locked_short_read` | Same explicit fault after real sharing denial and release | Open recovery followed by immediate SHORT_READ rejection |

The timeout fixture supplies a 2.5-second remaining slot deadline; other cases
supply 10 seconds. Both are fixture data. Production timeout constants and both
reader deadline checks are unchanged. The result must retain exactly the same
deadline before and after polling. This tests enforcement of the existing
absolute deadline, not the duration of a full 600-second START or 30-second ACK
wait. The original heartbeat continues through the inherited `_process`; the
validator retains the existing two-second gap bound.

Every ordinary case executes byte-identical candidate code. A deterministic
short read cannot be reliably forced by racing a real file length change, so
the two explicitly named short-read cases add exactly one buffer-resize line
after each of the candidate's two `get_buffer(size)` calls in the disposable
project only. Removing the exact inserted bytes must restore the original
candidate, including its newline bytes. Both hashes, the injected flag and the
exact reversal result are frozen. These cases prove the existing length-check
and failure path, not an actual operating-system short read.

Valid payloads use the existing host `publish()` implementation by delegation.
Malformed/size inputs use an explicitly labeled invalid-byte publisher with
exclusive temporary file, flush/fsync/close, no-overwrite rename and byte
readback. The host obtains any fixture handle before arming the reader, so the
normal reader cannot race past the intended sharing condition. Holding DELETE
access is a deliberate mechanism fixture; it does not claim the same handle
was present at the S96 failure.

Expected negative cases retain the original `_fail()` artifact and actual
native exit 86. The helper independently captures the same process exit and
also returns 86. The supplemental capture checks the actual PID/exit, zero
descendants before cleanup, joined output drains, source bytes, and checked
Job/process-handle closure. It deliberately does not call the owner's
success-only `finish()` or manufacture its accepted capture schema. The
owner's `BENCHMARK_CLOSED_BEFORE_FINISH` classification remains in cleanup
evidence and is documented as part of this diagnostic path.

Open-failure logs must be exactly pending+recovered or pending+terminal. The
first error, time and frame must remain identical across those records. The
last logged attempt must equal the final attempt count, proving no retry
occurs after a successful open that subsequently fails receipt validation.
The fixture samples only fixed primitive first/last pending ObjectDB and
resource counts; it creates no per-frame array or file/log record. Those
whole-editor counts are retained observations, not a memory plateau verdict.

Retain failed runs. Repair only the explicitly owned source/helper, freeze a
fresh helper hash, and use a new run ID; never overwrite or relabel prior
evidence. The S96 coupled helper cannot be rerun as if its old closure still
covered this changed candidate.
