# GT-09 candidate checkpoint — 2026-10-08

`AUTHORITY=0` · `ACCEPTANCE=false` · `final_frozen_source_hash=38c01d56596434d4738af9ad87e75dfbe312e4241d2eac03f4fd3247efcbfdff`

This package records the latest coordinator checkpoint. It is not a GT-09 acceptance: both fixture manifests are candidate-ready, external MCP transport is measured only, while native adapter/dependency closure, the exact model/host matrix, and two independent critic decisions remain open.

## Candidate evidence

- Room fixture: `studio/.local/reviews/gt09-playtest-20261008-12/room/manifest.json` — `PLAYTEST_EVIDENCE_READY`, source closure `a0ea0ec124cb5a8e4fcc0b722345143802c496603e543f82eed9ed97f1de2529`.
- Arena fixture: `studio/.local/reviews/gt09-playtest-20261008-13/arena/manifest.json` — `PLAYTEST_EVIDENCE_READY`, source closure `af2e73605f5594269b5beec6ecec4be9ba156645e594e1a435164f6765d529b5`.
- MCP transport receipt: `studio/.local/reviews/gt09-mcp-spike-20261008.json` — `MEASURED_TRANSPORT_ONLY` for the two exact pinned servers; no Godot/Blender process was launched.
- MCP matrix: `studio/.local/reviews/gt09-mcp-capability-matrix-20261008.json` — `EXTERNAL_TRANSPORT_MEASURED_NATIVE_OPEN`; native fixture and public capability remain unclaimed.
- Adapter diagnostic: `studio/.local/reviews/o2-adapter-gt09-20261008-02` — retained `DIAGNOSTIC_FAIL`, no blind retry.
- Dependency diagnostic: `studio/.local/reviews/gt09-dependency-20261008-08` — retained diagnostic, not clean closure proof.

## Review gate

Two read-only critics using different models must inspect this exact package and return explicit `TICK=yes` or `TICK=no`. Any source change requires a new package hash and fresh fixture evidence.

The 2026-10-08 pair both returned `TICK=no`: [critic-astra.md](critic-astra.md) and [critic-sol.md](critic-sol.md). Their reports are historical for the pre-binder candidate. A fresh critic pair is required for this exact hash. Historical native conformance is now linked as `CANDIDATE_PASS` on stale closure `c91bc0d7…`; it is useful replay/save-reload/perf evidence but cannot satisfy current frozen-source binding. The substantive blockers remain native adapter/dependency closure, exact model/host capability coverage, and current-closure command-ID proof. GT-09 remains `IN_PROGRESS`; no checkbox was changed.


External transport measurement (authority 0): `studio/.local/reviews/gt09-mcp-spike-20261008.json` measures both exact pinned stdio servers with two clean sessions, retry, reconnect/context reset and a negotiated unsupported protocol outcome. The matrix is `EXTERNAL_TRANSPORT_MEASURED_NATIVE_OPEN`; native fixture, command/lease, model-host and critic gates remain open.

The source binder is [`source-manifest.json`](source-manifest.json), sha256 `048069f3a3e9b63c90040b879d637ce3a5b1d7f305416b6eeef6e926e69f4f2e`. It binds both fixture closures, shared host files, binary pins, verifier files, and evidence reference hashes.
