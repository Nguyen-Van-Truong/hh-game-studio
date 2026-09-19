# S100 import-only diagnostic result

The cold import completed in **5.235 seconds** with the original 20-second wall,
15-second Job CPU, 2 GiB and four-process limits. It did not reproduce S100's
startup timeout. This does not explain the historical timeout, establish campaign
acceptance, or resolve S98's separate command status-gap failure.

The exact source closure was `cfc4b55a5407891bfd54d22d9f1ac45a74b6c744898199a0e4690d6230a6c1d6`.
The executed frozen driver was `afcf7ecab14f5e079d768c02e3ed34615bd70f976ceb3321fc3c39879f368174`.
The original source, copied source and driver remained unchanged. The exact 15-file
initial fixture was copied without `.godot` cache. Native arguments were unchanged
apart from the fresh project path; no campaign was activated.

Godot target **10424 exited 0**, independently recorded by its helper and retained
observation handle. Import helper **21920 exited 0**. The outer diagnostic target
**51304 exited 0**, and its helper exited **0**; that outer helper's PID was not
persisted by `BenchmarkProcess` and remains unknown. The outer elapsed time was
6.672 seconds under the separate 90-second host watchdog. Both import and outer
Jobs reached natural zero before cleanup and closed with no retained Job handle,
taint or native error. Import helper, target observation and outer wrapper handles
were released. No launcher self-exit is inferred from its own file.

There were **45 samples**, zero observer errors, zero cleanup errors and zero
dropped events. The configured interval was 100 ms; observed intervals were
105.952–110.088 ms. Host events showed 495.673 ms from stage entry to helper creation
(outside the native stage's wall timer), 25.159 ms from helper creation to stdin
close, then 247.033 ms until the target-start receipt was observed. First output
was read 438.867 ms after stdin close. Another 3,521.200 ms elapsed before the first
filesystem-scan output. These are host observation times, not instruction-level
engine timing.

Across the sampled 4.755 seconds, target counters rose by 4,093.75 ms user CPU,
1,093.75 ms kernel CPU, 186,375 page faults, 14,212,197 read bytes and 3,302,094 write
bytes. Peak observed working set was 650,022,912 bytes and private commit was
582,295,552 bytes. CPU is aggregate across threads and may exceed wall time; faults
include soft faults. This is a progressing successful startup, not evidence of the
specific condition that blocked S100.

`result-analysis.json` binds every cited raw artifact by length and SHA256. Raw
files under `run-01` are unchanged. This result remains diagnostic-only and
ineligible for the acceptance dataset.
