# M-1e MCP hello spike

Spike only. Not `crates/gs-mcp`. Do not treat this as production.

## Pin

| Item | Value |
| --- | --- |
| Crate | `rmcp` (official Rust MCP SDK, [modelcontextprotocol/rust-sdk](https://github.com/modelcontextprotocol/rust-sdk)) |
| crates.io pin | **`rmcp = "=3.1.2"`** (Cargo.toml, not a floating `^` / latest) |
| Companion | `rmcp-macros = 3.1.2` (pulled by `rmcp` macros feature) |
| Git tag | `rmcp-v3.1.2` |
| Git commit | `02c62aef2e331e5cf79c06c744eb1eb052cc8ebd` (tag object `bb4fd3d227a627c1b2ee988a1ee4a20948dd8b2a`) |
| Published | 2026-08-07 |
| Features used | `server`, `macros`, `transport-io` (stdio) |
| Host rustc | `1.93.1` (rmcp 3.1.2 MSRV is 1.88) |

`Cargo.lock` is generated next to this crate (82 packages locked). Repo-root `.gitignore` currently ignores `Cargo.lock`; the **authoritative pin is the `=3.1.2` line in Cargo.toml**. Re-record the lock at G1 into `docs/VERSIONS.md`.

## What it does

- stdio JSON-RPC MCP server (`GsMcp.serve(stdio())`).
- Hello: `initialize` → `serverInfo.name = "mcp-spike"`, `version = "0.1.0"`, tools capability on.
- One tool: `gs_command`.
  - Input: `{ "method": string, "params": <any JSON> }`
  - Result: echo of those two fields (text JSON + `structuredContent`).

No editor bus, no registry, no extra tools.

## How to run

From repo root:

```
cargo run --manifest-path experiments/mcp-spike/Cargo.toml
```

From this directory:

```
cargo run
```

The process speaks MCP on stdin/stdout. Do not print logs to stdout.

Verify:

```
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo build
```

## MCP Inspector (for a human later)

Inspector was **not** run in this environment. Exact command from repo root, after `cargo build` in this crate:

```
npx @modelcontextprotocol/inspector -- experiments/mcp-spike/target/debug/mcp-spike.exe
```

Or let Inspector build/run via cargo (slower first time):

```
npx @modelcontextprotocol/inspector -- cargo run --quiet --manifest-path experiments/mcp-spike/Cargo.toml
```

In Inspector: Connect (stdio) → List Tools → expect `gs_command` → Call with e.g. `method=session.hello`, `params={"ping":true}` → expect the same values echoed.

Cursor `mcp.json` (also **not** tested here):

```json
{
  "mcpServers": {
    "hh-gs-mcp-spike": {
      "command": "cargo",
      "args": [
        "run",
        "--quiet",
        "--manifest-path",
        "experiments/mcp-spike/Cargo.toml"
      ]
    }
  }
}
```

## What was actually tested (2026-08-16)

| Check | Result |
| --- | --- |
| `cargo test` | **pass** — 3 unit + 1 stdio integration |
| `cargo clippy --all-targets -- -D warnings` | **pass** |
| `cargo fmt --check` | **pass** (after `cargo fmt`) |
| `cargo build` (debug) | **pass** |
| Raw stdio handshake (PowerShell → `target/debug/mcp-spike.exe`) | **pass** (transcript below) |
| MCP Inspector | **not run** |
| Cursor MCP | **not run** |

`cargo test` names:

- `hello_server_info`
- `list_tools_exposes_gs_command_schema`
- `gs_command_handler_echoes_method_and_params`
- `stdio_initialize_list_tools_and_echo` (spawns the binary; initialize + `tools/list` + `tools/call`)

## Stdio handshake transcript (this machine)

```
>>> {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"notes-handshake","version":"0.0.1"}}}
<<< {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25","capabilities":{"tools":{}},"serverInfo":{"name":"mcp-spike","version":"0.1.0"},"instructions":"HH Game Studio M-1e hello spike. One tool: gs_command (echo)."}}
>>> {"jsonrpc":"2.0","method":"notifications/initialized"}
>>> {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
<<< {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"gs_command","description":"Spike echo: returns {method, params} unchanged. Production will forward to the editor bus.","inputSchema":{"$schema":"https://json-schema.org/draft/2020-12/schema","properties":{"method":{"type":"string"},"params":true},"required":["method","params"],"type":"object"}}]}}
>>> {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"gs_command","arguments":{"method":"session.hello","params":{"ping":true}}}}
<<< {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"{\"method\":\"session.hello\",\"params\":{\"ping\":true}}"}],"structuredContent":{"method":"session.hello","params":{"ping":true}},"isError":false}}
```

## Lessons for G1 / `docs/VERSIONS.md`

- Official SDK crate name is **`rmcp`**, not a crate literally named `rust-sdk`.
- 3.1.2 implements MCP `2026-07-28` and accepted a `2025-11-25` initialize from this client.
- `params: serde_json::Value` schemas as JSON Schema `true` (any JSON). Fine for a generic `gs_command`.
- Keep the pin exact; do not float on `main`.
