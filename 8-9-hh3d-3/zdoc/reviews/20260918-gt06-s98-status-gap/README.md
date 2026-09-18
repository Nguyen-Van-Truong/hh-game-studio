# S98 status-gap failure attribution

Campaign: gt06-s98-campaign-01, run gt06-s98-campaign-01.r00.a01.

Result: FAILED at batch 17 after 18 complete batches because host command stream reached max_status_gap_ms=2043.7348, above the locked 2000 ms gate. The native ACK/joint row remained valid (594.998 ms, ObjectDB 71128, resources 6), with zero dropped commands/telemetry. Cleanup observed zero active jobs, closed owners, released handles and no native error; host wrapper exit 1 and editor wrapper exit 2.

This packet is derived from immutable raw files. It is diagnostic only, not PASS, not a no-leak claim, and not eligible for the GT06 dataset. Root cause is unproven. Preserve all 18 batches and diagnose owned-workload/environment attribution before any fresh campaign; do not loosen the gate or retry blindly.

The triggering command was admitted.96: lookup timed out at getresponse after 2002.5627 ms, then its retry recovered READBACK_CONFIRMED. This identifies the gate trigger, not the OS/server/lock root cause.

Derived packet: attribution.json (SHA256 7b9f4f6fe4702c6bd9e2df6f1cb8f85dcef9fa29e01b9e0fa4956935b2ea3ca6).

Terminal reconciliation: terminal-reconciliation.json (SHA256 1bad488b993dd3082ab8fb008a55f1e032cfccb7f9d59122559a9a71bba83dda). Scheduler state 3/result 1 is recorded; missing editor-target and supervisor natural exits remain UNKNOWN, so this is not PASS or natural-exit proof.
Workstation preflight: workstation-attribution-preflight-01.json (SHA256 28609498f97969d1609b69c50b84c30c60e1cc7c1379ee72cbfa4cc3d880c5eb). It is a read-only post-terminal snapshot with no owned HH3D/Godot workload alive; causal attribution is unavailable and the artifact is not acceptance evidence.
