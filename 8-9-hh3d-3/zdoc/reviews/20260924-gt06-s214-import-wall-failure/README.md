# S214 — S213 import-stage wall-limit terminal

S213 (`gt06-s213-formal-01`) terminated before batch 0 because the Godot import stage hit the existing 20-second bounded wall limit (`STAGE_WALL_LIMIT`, elapsed 20.297 s). Raw and supervisor evidence are sealed by the manifest and archive. The import observer recorded 185 samples, no target exit receipt, released its probe handle, and no cleanup error; scheduler state is not treated as an exit proof.

This is Authority 0 diagnostic evidence only. It does not prove a leak, ownership, root cause, or GT06 acceptance. No partial batch is merged. The timeout, baseline, profile, counter/RSS gates, and formal 10×35 contract remain unchanged. A future repair must be tied to a proven import boundary and use a fresh campaign ID.
