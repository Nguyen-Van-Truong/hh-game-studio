# S98 status-gap failure attribution

Campaign: gt06-s98-campaign-01, run gt06-s98-campaign-01.r00.a01.

Result: FAILED at batch 17 after 18 complete batches because host command stream reached max_status_gap_ms=2043.7348, above the locked 2000 ms gate. The native ACK/joint row remained valid (594.998 ms, ObjectDB 71128, resources 6), with zero dropped commands/telemetry. Cleanup observed zero active jobs, closed owners, released handles and no native error; host wrapper exit 1 and editor wrapper exit 2.

This packet is derived from immutable raw files. It is diagnostic only, not PASS, not a no-leak claim, and not eligible for the GT06 dataset. Root cause is unproven. Preserve all 18 batches and diagnose owned-workload/environment attribution before any fresh campaign; do not loosen the gate or retry blindly.

Derived packet: attribution.json (SHA256 ce20bdf8f9b6586614c9b3035b30cf7ff8b77d51f75826b07026b8a7ebab0f11).
