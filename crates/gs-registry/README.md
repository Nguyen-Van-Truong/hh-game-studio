# gs-registry

Executable method contract (MASTER 4.0). Source of truth for bus methods.

Does **not** apply commands or talk TCP. Generates `docs/PROTOCOL.md`.

## API

- `MethodSpec` — `name`, `side_effect`, `undo`, `capability`, `idempotency`, `errors`, `emits`
- `SideEffect` — `Mutating` | `ReadOnly` | `Job`
- `Undo` — `Auto` | `None` | `Special(&'static str)`
- `Capability` — `Base` | `Destructive(&'static str)` | `UiOnly`
- `Idempotency` — `ByCommandId` | `Natural` | `NotApplicable`
- `all_methods() -> &'static [MethodSpec]`
- `get(name) -> Option<&'static MethodSpec>`
- `method_count() -> usize`
- `generate_protocol_md() -> String`
- `write_protocol_md(path)`
