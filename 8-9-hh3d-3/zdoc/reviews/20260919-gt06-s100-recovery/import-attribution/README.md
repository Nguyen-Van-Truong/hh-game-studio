# S100 cold import attribution

This is a diagnostic only. It is ready for the coordinator to launch after the
other owned workload is terminal. It never resumes S100 or runs benchmark batches.

From the repository root, validate the pins without launching an engine or child:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s100-recovery/import-attribution/probe.py --check
```

The tiny ABI self-check opens a retained observation handle to its own current
Python process, queries actual CPU/memory/I/O counters, then checks equal handle
counts and unchanged threads after closing it. It also checks exact `Popen`,
`PIPE`, `CREATE_NO_WINDOW` delegates and in-memory bootstrap/output byte forwarding.
It starts no observer thread, subprocess or engine:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s100-recovery/import-attribution/probe.py --selfcheck
```

Preflight fixes use six 64-bit `c_uint64` I/O counters (48-byte structure) and
include the unchanged `subprocess.PIPE` constant in the stage delegate. The
retained `selfcheck-01.json` binds the executed check to the final driver hash.

The coordinator may then launch exactly one cold import:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s100-recovery/import-attribution/probe.py --launch
```

`run-01` is created exclusively; a second launch fails rather than overwriting it.
The launcher verifies the preserved manifest and current 51-file source closure,
copies those exact source files, copies all 15 initial S100 project files, verifies
the pinned Godot binary, and freezes this driver. The original inert binding stays
byte-identical; this is not reuse of a campaign run identity for acceptance.
No `.godot` cache is copied. The original headless `--editor --path ... --import`
arguments and bootstrap bytes are unchanged apart from the new project path.

The child invokes the frozen `native_job.run_trusted_stage` with its original
20-second wall, 15-second Job CPU, 2 GiB, four-process and log/workspace caps.
Small delegate taps observe host Popen, Job configuration and pipe operations;
they do not change the delegates, engine arguments, source files or limits.
The existing `BenchmarkProcess` owns the child and descendants with six aggregate
process slots. An additional 90-second outer host limit bounds setup plus import;
it does not extend the inner import deadline. Existing cleanup grace still applies.

`attribution.json` contains monotonic startup/output events, 100 ms target CPU,
page-fault, working-set, private-commit, I/O and priority samples, and actual exit
observations from an identity-bound retained handle. It includes observer gaps,
dropped-event counts, source verification and handle cleanup results. These
observations distinguish gate delay from work/wait after target startup. They
cannot identify an I/O or scheduling cause by low CPU alone. No global traces,
process priority changes, engine configuration changes or thread suspensions occur.

`import-host/capture.json` remains the unmodified stage capture. A retained-handle
exit after cleanup is an actual forced exit, not natural completion. Without a
pre-cleanup natural-tree observation and helper receipt, natural exit is `UNKNOWN`.
`host-owner/` holds the pinned outer target/helper exits and checked cleanup;
`outer-result.json` reports the outer observations. Exit zero from this diagnostic
means that observation and cleanup completed; always inspect `stage_error` and
the raw import capture for the import result. All artifacts remain ineligible for
the acceptance dataset.
