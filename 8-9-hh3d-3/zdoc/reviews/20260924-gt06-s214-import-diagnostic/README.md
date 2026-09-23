# S215 — S214 bounded import diagnostic

S214 diagnostic `gt06-s214-import-diagnostic-01` completed the bounded import/editor route under the existing 20-second stage limit. Import and editor both had actual exit 0, natural process-tree exit, closed zero-count jobs, released handles, and no cleanup error.

The diagnostic intentionally uses the 39-file `run_native_benchmark` closure (`6cabd778...306577`). The formal campaign uses the distinct 53-file `run_benchmark_campaign` closure (`6f6c96...bf8127`). These domains are not merged; any fresh GT06 formal run must bind the 53-file closure.

This is Authority 0 diagnostic evidence. It does not satisfy the 10 fresh pairs × 35 batches gate, does not prove leak ownership or root cause, and does not open GT07–GT10. It only supports one fresh bounded formal dispatch with unchanged gate, timeout, baseline, profile, counter and RSS policy.

Raw files: 119; raw manifest SHA256: `6e3395811085d8964c647c811a72d4761c9d09fe9b266f2c45688a6f6f39bfdc`.
