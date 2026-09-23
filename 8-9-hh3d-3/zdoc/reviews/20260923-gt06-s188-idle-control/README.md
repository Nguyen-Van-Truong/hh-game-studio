# S188 idle-editor control

AUTHORITY=0; diagnostic only; no GT06 acceptance.

The fresh run `gt06-s188-idle-editor-01` used pinned Godot 4.7.2 and a copied fixture. It performed one 720-second editor-idle window with no HTTP or native mutation cycles. A retained `ProcessProbe` sampled `GetProcessHandleCount` every 250 ms while the plugin recorded filesystem scanning/importing, ObjectDB and resource counters.

The target editor exited naturally with code 0; the driver exited 0; the owned Job reported zero active descendants, closed cleanly, no taint or failed native operation, and stderr was empty. Handle counts showed startup variation followed by a bounded, non-monotonic downward trend; this does not identify kernel-object ownership or prove absence of a leak. The S185 row-level +9 remains unexplained at ownership level.

`analysis.json` is derived from retained raw files under `studio/.local/reviews/gt06-s188-idle-editor-01`; raw logs are not committed. Keep the original GT06 10×35 gate and do not use this control as a formal run.
