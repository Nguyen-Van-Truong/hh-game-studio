# S160 source-ownership memo (read-only; AUTHORITY=0)

## Evidence

The HH Studio editor plugin creates a `StreamPeerTCP` only when the owned launch environment provides `HH_EDITOR_TOKEN`, validates the session/port, connects to loopback, and polls/send/receives in `_process`. `_exit_tree` disconnects the peer. The benchmark then performs the fixed Undo -> save_scene -> scene_saved -> reload -> readback sequence. The campaign's `CampaignProducer` is a resident host in the helper process; the editor target is a separate Godot process.

This gives a plausible shared subsystem boundary for Event/IoCompletion observations: the loopback bridge and Godot's Windows socket implementation may use synchronization and I/O completion objects. It is only source-path evidence. It does not identify which call created the retained PSS entries, prove that the plugin path is exercised in every failing batch, or prove a leak.

## Attribution status

S153 reproduced editor handle-counter growth without the S156 census; S156 observed Event+1 and IoCompletion+1 with editor 555 -> 557 while ObjectDB/resources stayed 71130/6. PSS documented fields do not supply creator timestamps or ownership. The S160 WPR memo found no documented per-owned-PID kernel handle filter, and the conditional `!htrace` fallback is unavailable on this host with no measured overhead. Therefore creator/owner remains `UNKNOWN`; no repair or formal retry is justified from this memo.

## Safe next action

Keep the exact source/profile/gates and the S160 launcher integration. If a supported debugger with `!htrace` becomes available, a fresh bounded diagnostic may inspect open/close stacks for the already-owned PID, with PID/start/executable binding and the original stop boundary. A missing stack, foreign context, generic kernel frame, or altered timing remains UNKNOWN. Do not run a count-only retry, disable IPC in a formal run, close handles manually, change thresholds, or claim GT06 acceptance.

## Files

- `studio/godot-addon/addons/hh_studio/plugin.gd` SHA-256 `13dc29df8b673358c40af96220b8d8c29e999eb9f9a2618b224a1e9d983b6036`
- `studio/tests/replay/benchmark_native.gd` SHA-256 `13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`
- `studio/tests/replay/run_benchmark_campaign.py` SHA-256 `2073fbbb9abb7a46c902a56ad251543932534519be07c844dca0858d2364dac6`

`ENGINE_STARTED=false`, `TRACE_STARTED=false`, `formal_acceptance=false`, `eligible_for_dataset=false`.
