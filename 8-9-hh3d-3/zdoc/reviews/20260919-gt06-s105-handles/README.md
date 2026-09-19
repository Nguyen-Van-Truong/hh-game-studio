# GT06 S105 owned-handle attribution supplement

This is a bounded, diagnostic-only supplement. It does not modify the frozen
GT06 runtime, profile, native source, acceptance gates, or any raw S102/S103
capture. It is not a formal campaign and cannot contribute F13/F14 samples.

## What is verified

`pss_adapter.py` observes only a caller-supplied retained
`ProcessProbe` handle. It re-checks PID, process-start identity and executable
on a separately opened observer handle, uses the documented Windows x64 PSS
handle-information walk, hashes object names instead of publishing them, and
closes marker, snapshot and observer handles exactly once. Numeric handle
values and matching attributes are explicitly not treated as object identity.
Any identity mismatch, count mismatch, budget expiry or cleanup uncertainty is
`UNKNOWN`; cleanup uncertainty latches and prevents a second capture.

The eight fake-API tests passed in `0.004s`. The reader-v104 regression and
boundary tests passed in `0.043s` (10 tests). A real self-check against the
current owned Python process passed with actual exit `0`: binding verified,
155/155 entries walked, observer and target cleanup released, and no error
records. This proves the adapter/ABI/cleanup path only; it does not attribute
the earlier Godot handle excursion.

## Limits and next step

The self-check is not a Godot workload and is excluded from benchmark data.
No formal GT06 retry is authorized by this packet. A future owned prefix may
capture exactly two supplemental snapshots (batch-4 baseline and the original
batch-5 gate point) after the original gate has been recorded and outside the
measured interval. It must bind each snapshot to the retained process
identity, source/profile hashes and sample receipt, and retain all actual exit,
Job, tree and handle cleanup results. The original counter/RSS/status-gap
gates remain unchanged. If the prefix cannot provide those bindings, it must
stop with `UNKNOWN` and preserve the raw evidence.

Pins remain:

* source checkpoint `56bfd448e83aa2512c0c2561e8e1e29f12134360`
* 53-file closure `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`
* profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`
* generated S103 overlay `bb137f32f1fae3730cc139f03fc6902813b3742d5a08d437e957e291cfe0ec46`

