# GT-09 independent critic — Sol — 2026-10-08

`TICK=no`

Reviewed the exact candidate package
`8-9-hh3d-3/zdoc/reviews/20261008-gt09-candidate-v6/gt09-candidate.json`.
This is an independent read-only critic decision. It does not grant authority,
change the plan, or convert diagnostic evidence into a public capability claim.

## Frozen package integrity

- The candidate declares `final_frozen_source_hash`\
  `d527e54c92eb46e8357aa1fcfc264bca46e1d93de97186a92cb48042f7cafb17`.
- The v6 source binder's file SHA256 is\
  `aee53e0821a708e7174b7958a8534b673c2d9d84db99458281f8b2a7dda8be13`.
  Removing `binder_payload_sha256` and hashing canonical sorted JSON recomputes
  the declared frozen hash exactly. The package and binder agree on the hash.
- Binder `git_head` `fd5ad2be059f754503aaff995ebc35b2d8b03624` matches the current
  checkout. The binder's plan and status hashes match the current plan and
  `studio/AUTHORING_STATUS.md`.
- All 241 `shared_host_files` and all 12 `verifier_files` listed in the binder
  exist and match their SHA256 values. The arena and room manifest SHA256 values,
  the registered-owner result and child-result hashes, native conformance,
  Blender handoff, MCP receipts, and plan/status references also match the
  package's recorded values.

The frozen bookkeeping is therefore internally coherent. That only proves the
package is reproducible; it does not satisfy the open GT-09 gates below.

## Evidence confirmed

The new registered-owner diagnostic is real useful progress. The recorded
`o2-registered-authoring-20261008-02` result (`dcb633da0d0734b3a74fde8d6a9312118b2...`)
observes a Godot transaction with 14 command IDs, `native_observed=true`,
`editor_diagnostic_pass=true`, actual editor process exit 0, UndoRedo do/undo/redo,
save/reload and typed node/resource readback, plus the Blender handoff hash. The
child saved-room result is `DIAGNOSTIC_PASS` (`bd98acc3...`). Both records are
correctly authority 0 with `public_ack=false`.

The two delegated fixture manifests are internally captured: arena run
`gt09-playtest-20261008-18` and room run `gt09-playtest-20261008-19` are
`PLAYTEST_EVIDENCE_READY`, each has host-captured Godot exit 0, decoded video and
clean bounded lifecycle evidence. Native conformance is recorded as
`CANDIDATE_PASS` with no verifier errors, and the shared Blender artifact is
hash-bound in both fixture paths.

## Mandatory gates still open

1. **Registered catalog E2E and AUTH gates.** The registered owner profile in
   `registered-owner-result.json` is explicitly `CANDIDATE_ONLY`,
   `runtime_enabled=false`, `script_enabled=false`, `public_ack=false`, and
   `authority=0`. The receipt proves one 3D room diagnostic transaction, not the
   public gameplay-source catalog. It does not prove the required 2D arena through
   that registered owner, nor AUTH-01..07. The private/native diagnostic path
   cannot substitute for two original fixtures completed entirely through the
   catalog.
2. **Generic dependency closure.** The package still records
   `dependency_closure=OPEN_DIAGNOSTIC`. The bound dependency capture has
   `dependency_closure_verified=false`, `dynamic_dependencies_verified=false`,
   `native_observation_verified=false`, and `validation_attribution_proven=false`.
   The scoped loader-literal inventory is narrower evidence and cannot close the
   whole runtime dependency requirement.
3. **External MCP and capability matrix.** The MCP matrix remains
   `EXTERNAL_TRANSPORT_MEASURED_NATIVE_OPEN`; external rows are transport-only,
   the model and host capability are unspecified, and no native fixture
   postcondition/lease/command-ID or unsupported-client rejection is proven. The
   unsupported-protocol probe was negotiated, not rejected. It cannot be marked
   `SUPPORTED` for GT-09.
4. **Owner playtest.** The fixture manifests identify
   `performed_by=agent`, `delegated_by=owner`, `playtest_claim=false` and
   `authority=0`. They are valid delegated scripted runs, but GT-09 requires an
   owner playtest of each fixture with an owner OK/notes record; delegated agent
   evidence cannot sign for the owner.
5. **Current conformance is still candidate evidence.** The native conformance
   pack is `CANDIDATE_PASS`, authority 0. It demonstrates useful input/physics,
   replay/save-reload/perf and Blender handoff, but it does not close catalog
   registration, generic dependency attribution, or the MCP matrix.
6. **Two independent same-hash critics.** The package itself leaves this
   requirement pending. This report is one independent `TICK=no` decision; no
   self-acceptance or checkbox change is justified.

The current plan header correspondingly remains `GT-09 IN_PROGRESS`, with
`OPEN=REGISTERED_PUBLIC_CATALOG_E2E,TRUSTED_DEPENDENCY_SCOPE,EXTERNAL_MCP_MATRIX,CRITICS`
and `NO_AUTH_OR_PUBLIC_CLAIM`. Since mandatory DoD items remain unproven,
`TICK=no` is the only valid decision for the exact v6 hash.
