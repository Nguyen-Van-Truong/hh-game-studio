# GT-09 critic A — candidate v6

`TICK=no` for the exact package
`8-9-hh3d-3/zdoc/reviews/20261008-gt09-candidate-v6/gt09-candidate.json`.

## Frozen-package integrity

I reviewed only the v6 package and current worktree. The source binder payload was recomputed by removing `binder_payload_sha256` and hashing canonical JSON (`sort_keys=true`, compact separators):

- declared and recomputed final source hash: `d527e54c92eb46e8357aa1fcfc264bca46e1d93de97186a92cb48042f7cafb17`;
- `source-manifest.json` SHA-256: `aee53e0821a708e7174b7958a8534b673c2d9d84db99458281f8b2a7dda8be13`, matching the package reference;
- package/source binder/current `git HEAD` all bind to `fd5ad2be059f754503aaff995ebc35b2d8b03624`;
- all 253 shared-host/verifier source file hashes in the binder matched the worktree (0 missing, 0 mismatched);
- arena and room playtest manifest hashes, native conformance hash, registered-owner outer result hash, child result hash, Blender handoff hash, adapter result hash, MCP spike/matrix hashes and plan/status hashes matched their declared references.

The two delegated playtests are valid candidate evidence: both manifests are `PLAYTEST_EVIDENCE_READY`, `performed_by=agent`, `delegated_by=owner`, actual Godot exit 0, decoded video, clean owned process trees and no recorded errors. This evidence remains authority-zero and `acceptance=false`.

The new registered-owner diagnostic is also real native evidence: `o2-registered-authoring-20261008-02` and child `o2-saved-room-registered-20261008-02` both report actual editor exit 0 and clean cleanup; 14 command IDs, transaction digest, lease/fencing, UndoRedo do/undo/redo, save/reload/readback, typed 3D/resource checks and Blender handoff are bound and hash-consistent. Its receipt explicitly says `state_kind=NATIVE_OBSERVED_AUTHORITY0`, `public_ack=false`, `runtime_authorized=false`; profile status is `CANDIDATE_ONLY` with `runtime_enabled=false`.

## Blocking findings

### P0 — Registered public catalog/AUTH gate is still open

The plan GT-09 DoD (plan lines 1175–1190) requires the two mini-game fixtures to be authored through the catalog and the AUTH contract to be verified. The registered-owner result proves a candidate native transaction path for one room graph, but it does not register a runtime-enabled profile, grant public capability, or provide AUTH-01..05 evidence. The package itself records `registered_catalog_e2e=OPEN_CANDIDATE_ONLY_PROFILE`, `authoring_transaction_seam=NATIVE_OBSERVED_AUTHORITY0`, `authority=0`, and `acceptance=false`. No native registered arena catalog run is present. A critic cannot tick while this mandatory gate is explicitly open.

### P0 — Complete trusted dependency closure is not proven

`gt09-dependency-20261008-08` remains diagnostic. Its capture and observation both report `dependency_closure_verified=false`, `dynamic_dependencies_verified=false`, `validation_attribution_proven=false`, `public_ack=false`, and `authority=0`. The newer scoped loader-literal inventory does not establish complete runtime dependency attribution required by GT-09/TQ00/TX11. The package correctly labels this `OPEN_DIAGNOSTIC`; promoting it to PASS would contradict the captured postconditions.

### P0 — MCP/client/model/host conformance is incomplete

`gt09-mcp-capability-matrix-20261008.json` is `EXTERNAL_TRANSPORT_MEASURED_NATIVE_OPEN`. Both pinned external servers only have stdio handshake/list/reconnect observations; `model=UNSPECIFIED`, native fixture/postcondition/lease/hash checks are unmeasured, and the unsupported protocol was negotiated rather than rejected. The private adapter row is explicitly not an MCP compatibility claim and has unspecified model/host. GT-09 requires a measured client/model/host capability matrix on an independent fixture; this gate is open.

### P0 — Two same-hash independent critic approvals do not exist yet

The package requirement is `two_critics_same_final_hash=PENDING`. This report is one read-only critic only; no second v6 critic decision is present. A worker cannot self-accept and the package says `acceptance=false`.

## Decision and next safe action

`TICK=no`. Keep `AUTHORITY=0` and do not tick GT-09 or open GT-10-PC. The next safe sequence is: register the candidate profile through the real catalog/runtime path and run fresh native arena + room AUTH evidence with public capability still fail-closed until all AUTH gates pass; close full dependency/dynamic attribution; run the actual pinned MCP client/model/host fixture matrix with rejection and postcondition checks; remint a package on the unchanged frozen source; then obtain two independent read-only critics on that exact package hash. The v6 package is internally sealed, but it is not an acceptance package.
