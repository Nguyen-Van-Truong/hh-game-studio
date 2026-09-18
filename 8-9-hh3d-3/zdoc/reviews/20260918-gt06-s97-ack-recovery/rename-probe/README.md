# S97 deterministic rename-sharing probe — unexecuted preparation

AUTHORITY=0. One owned pinned Godot 4.7.2 headless script reads a controlled
40-byte fixture, not an ACK or production file. No runtime source is changed.

Run from root's bounded owned Python lane (outer timeout 90s):

```text
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s97-ack-recovery/rename-probe/rename_probe.py --run
```

`--describe` only prints actual source/helper/binary/input pins. `--run` exclusively
creates `rename-probe/run-01`; do not reuse that path after an attempt. The parent
poll watchdog is 30s, the reader's wait for release is 15s. Original BenchmarkProcess
Job/CPU/memory/ownership limits remain unchanged; its longer generic wall setting
is bounded here by this parent and root's outer owned runner. Root captures the
orchestrator's actual exit separately; its self-written result cannot do so.

The probe fsyncs/closes a staged file, opens DELETE access with read/write/delete
sharing, uses real `SetFileInformationByHandle(FileRenameInfo)` to rename it,
and deliberately retains the DELETE handle. Controls compare:

- normal Godot READ while Python holds another read-only file handle;
- complete bytes through a Win32 reader that shares DELETE while the holder lives;
- Win32 READ without delete sharing, recording its actual OS error;
- actual pinned Godot `FileAccess.open`/`get_open_error` before holder release;
- the same Godot process reading/hashing the unchanged file after explicit release.

The holder is released only after the retained Godot `HH_S97_HELD` output. A
release marker coordinates the second observation; no content/clock/ACK is
fabricated. Each Win32 handle and Python control handle is explicitly closed,
including exception cleanup. Native target/helper PID/exits, Job state and
wrapper-handle/drain proof come from the original owner capture and final result.

This constructs a documented sharing state with a controlled lifetime. It does
not prove MoveFileEx overlapped S96's failed read, identify an antivirus actor,
or distinguish S96's unrecorded null-open from its unrecorded short-read branch.
Success shows the mechanism is possible on this pin; a failed control remains
evidence and is not silently retried. Native inputs have separate known byte
hashes; they are excluded from the source map while deliberately opened with
DELETE access, since ordinary Python readback would itself face that conflict.
No benchmark acceptance or root-cause certainty follows from this probe.
