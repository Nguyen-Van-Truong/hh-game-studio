# S225 — external RSS sampler diagnostic

Authority is `0` and formal acceptance is `false`. This is a bounded 90-second idle editor diagnostic, not a GT06 benchmark continuation. The observer is a separate process and binds PID, process-start identity, executable image, `GetProcessMemoryInfo.WorkingSetSize`, and `GetProcessHandleCount` through one retained process handle.

The target exited 0, the sampler exited 0, and the owned Job was zero/closed with no retained wrapper handle. The observer collected 360 samples: RSS ranged from 88,567,808 to 747,745,280 bytes and handles from 405 to 573. The idle plugin emitted 91 rows; ObjectDB rose from 70,990 to 71,115, resources from 5 to 6, and only the first row reported filesystem scanning.

This route proves that an independent RSS sampler works and that this idle fixture can accumulate output/object state. It does not prove a leak owner, kernel cause, collector defect, or the cause of S218’s formal batch-5 failure. The formal timeout, baseline, +10% RSS gate, counters, profile, and GT07–GT10 dependency remain unchanged.
