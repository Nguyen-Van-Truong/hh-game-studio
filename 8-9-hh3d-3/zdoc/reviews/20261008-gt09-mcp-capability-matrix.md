# GT09 MCP capability and reconnect matrix — 2026-10-08

`AUTHORITY=0`, `acceptance=false`. This is a read-only, fail-closed matrix
generated from retained GT09 private-adapter evidence. It does not start an
engine, Docker, Blender, MCP server, or network client, and it does not sign
GT09.

## Input and command

- Receipt: `studio/.local/reviews/o2-adapter-gt09-arena-20261007-01/result.json`
- Receipt SHA256: `7fb0c2fa9d40b0d75c557b4a465f5470dc168d5e33498ddb831774d4fe7d5001`
- Source closure: `d9bda850561fcd56132a96965657ddee4d456b803042bc1df6da488d72509e53`
- Native source jobs observed by that receipt: `2`, each with host/container/wait exit `0`
- Matrix JSON: `zdoc/reviews/20261008-gt09-mcp-capability-matrix.json`

Reproduce the offline check from the tools root:

```text
python -B studio/tests/conformance/gt09_mcp_compatibility.py `
  --receipt studio/.local/reviews/o2-adapter-gt09-arena-20261007-01/result.json `
  --output zdoc/reviews/20261008-gt09-mcp-capability-matrix.json
```

The expected exit is `2` while the external spike remains open. That is an
intentional gate result, not a process failure: the output status is
`INCOMPLETE_EXTERNAL_SPIKE`.

## What is measured

The private typed owner/adapter receipt independently records readback-bound
publication, two sequential native jobs, reconnect and context-reset lookup,
unsupported client-version rejection, owner-edit conflict preservation, and
no duplicate native dispatch. Public discovery is empty and the receipt
explicitly says `full_mcp_conformance=false`, so this row is labelled
`MEASURED_PRIVATE`, never `SUPPORTED_MCP`.

| Row | Status | Meaning |
| --- | --- | --- |
| `hh-private-python-adapter` | `MEASURED_PRIVATE` | Private typed adapter facts above; client `pc-godot-4.7.2`; model/host were not captured by this probe. |
| `NPGameDev/godot-mcp-toolkit` at `10a4508e880244c66a3f04861b2e22872c307247` | `UNMEASURED` | Pinned research reference only; no installation or fixture run. |
| `hybridindie/godot-mcp` at `48f34e7d28d65cfea456cc2641e13c3058caa3d6` | `UNMEASURED` | Pinned research reference only; no installation or fixture run. |
| `hh-public-catalog` | `DISABLED` | Private adapter discovery returned no public capabilities. |

## Remaining gate

The matrix intentionally leaves the external pinned MCP compatibility spike and
model/host capability rows open. A future scoped run must record the exact
client, model, host, addon/bridge version, transport/auth mode, command IDs,
pre/postconditions, reconnect/retry behavior, unsupported-version rejection,
and actual process exits on an isolated fixture. Documentation or README
claims cannot fill that row. Two independent critics must later review one
final source/review/raw hash; this file is not either critic signature.
