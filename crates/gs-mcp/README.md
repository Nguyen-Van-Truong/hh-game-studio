# gs-mcp

Production stdio MCP server (MASTER 10.4 / T8.1). Absorbs `experiments/mcp-spike`
without depending on it.

- Tool list is **generated from `gs-registry`** (one MCP tool per catalog method)
  plus generic `gs_command` and convenience `gs_screenshot`, `gs_events_poll`,
  `gs_run_test`.
- `gs_command` forwards `{method, params}` to the editor bus — any registry
  method, and later bus methods not yet in the catalog (`obs.*`, `judge.*`).
- Connects like `gs-cli`: `.gs/runtime/endpoint.json` under `GS_ROOT` / `--root`.
- Pin: `rmcp =3.1.2` features `server`, `macros`, `transport-io`.
- Never writes the bus secret to stdout, logs, or tool schemas (I8).
- `gs_screenshot` returns MCP image content only when a real PNG exists.
  `no_gpu` is a structured error — no placeholder PNG.

```
cargo run -p gs-mcp -- --root <project>
```
