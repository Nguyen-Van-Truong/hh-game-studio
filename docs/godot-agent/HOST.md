# Agent Host (R2-WP7)

The **Host** is the only layer that calls a model and decides the tool loop.
The sidecar (`bridge/`) and the editor plugin stay **deterministic execution**.
They do not hold model keys, do not pick the next tool, and do not “infer” a
plan by themselves.

This WP does **not** drive Godot. Mutate tools stay `E_UNVERIFIED`. Scene
writes belong to later R3 work.

## Who is the Host

| Mode | Process | When |
|------|---------|------|
| Interactive | The Codex / Cursor / Claude **client** is the Host | A person is in the IDE |
| Unattended | This repo’s `host/` Node process | CI, overnight, R7 90-minute sessions |

`host/src/host.ts` `Host` is the shared class. `--mode interactive` and
`--mode persistent` use that class so the same `{task_id, command_id, tool, result}`
comes out of both paths for the same fake-model script.

R7 needs a process that is clearly responsible for a 90-minute session.
MCP stdio is not that process.

## Persistent session (90 minutes)

State lives under the user store, never the Godot project tree:

`%LOCALAPPDATA%/HHGodotAgent/hosts/<session_id>/state.json`

Fields:

- `started_at`
- `deadline_at = started_at + 90 * 60 * 1000`
- `task_id`, `command_id`, `session_id`
- `plan` summary and `context_summary` (not an infinite chat transcript)
- `inflight` tool + `command_id` so kill/resume can continue
- `heartbeat_at`, `wakeup_at`, `handoff` (pid → pid)
- `budget` (`max_steps` / `used_steps`) and `cancelled`

Wakeup after kill is `--resume <session_id>` in a **new process**. Compact
drops `transcript` and keeps task / command_id / plan.

## Providers and credentials

| Provider | Network | Credential |
|----------|---------|------------|
| `fake` | None. In-process scripted turns. | Not required. |
| `configured` | Does not open a network session in this pin. | Required. |

Credential comes from the OS/user store only:

- `%LOCALAPPDATA%/HHGodotAgent/credentials/<provider>.json`
- or env `HH_HOST_CREDENTIAL` (tests)

Never from `project.godot`, `.hh-agent/`, or the git tree. Missing credential
is typed `{code:"E_EXTERNAL", message, path:"credential"}` and a non-zero
exit. Official tests use the fake model — no live API.

The sidecar never stores these keys.

## Tool loop

1. Host asks the provider for the next turn (tool or done).
2. Host persists `inflight.command_id` before executing.
3. Host runs a fake executor (tests) or may speak sidecar MCP
   (newline JSON-RPC `tools/call`, same shape as `tests/bootstrap/test_session.py`).
4. Host records `{task_id, command_id, tool, result}` and continues.

`--hold-after-decision` persists that in-flight command and keeps the process
alive so a test can kill it and `--resume` in a second process.

Budget exhaustion is `E_POLICY` (`path: budget`). `--cancel` is `E_CANCELLED`.
Deadline is `E_TIMEOUT`.

## CLI

```text
node host/dist/main.js --provider fake --mode persistent
node host/dist/main.js --resume <session_id>
node host/dist/main.js --show|--compact|--cancel <session_id>
node host/dist/main.js --provider configured
```

Logs go to stderr and are redacted. `state.json` is written through
tmp+rename and stripped of token/secret keys.
