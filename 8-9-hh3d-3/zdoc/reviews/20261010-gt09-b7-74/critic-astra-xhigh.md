# GT-09 final -74 independent critic (Astra xhigh)

## Verdict

**TICK=yes**

This is a read-only audit of the frozen GT-09 final package. I inspected the applicable nested `8-9-hh3d-3/AGENTS.md`, O13.1–O13.5/O13.9, the final manifest and hash, the Scheduled Task receipts, every K1–K15 row/exit receipt, producer outputs, K9 repair/replay evidence, K13 capability/provenance, K15 lifecycle evidence, and the frozen source at `573f3ce8`. I did not edit source or plan files and did not run an engine/producer.

## Frozen identity and closure

- Run: `gt09-matrix-final-20261010-74`.
- Manifest SHA256: `8d9a2ec6de47bace6390d7320ed3cc256010b4b352c21c66c8600095abe3d5be`; `manifest.sha256` matches.
- Matrix closure: `sha256:6b7b5231291a15c2db2672a8ed6a2a6d9f13219ac8d565f86c5d8e9ef2ee6650`.
- Recomputed source closure has 785 files, byte-for-byte matches both manifest payloads, and closure start/end are identical. The current source closure recomputes to the same digest.
- The tools plan explicitly pins Godot `4.7.2-stable` (O9.8 and `GT01_PIN_DECISION=GODOT_4.7.2_STABLE_OFFICIAL`); the 4.7.2 executable/hash recorded by this package is therefore the applicable pin for this tools-plan scope.

## Matrix and process evidence

Every row K1–K15 is `PASS`; every persisted row receipt has `actual_exit=0`, `timed_out=false`, `owned_tree_zero=true`, and all child steps exit 0 with native/host evidence where required. The final `--verify-only` audit was run with the module entry point and returned exit 0 with `status=DIAGNOSTIC_OK` and `errors=[]`; it only read evidence and did not rewrite the package.

The Scheduled Task was a real detached task, not a shell child. Its receipt records `actual_process_exit_observed=true`, `returned_exit_code=0`, elapsed `2487.203` seconds, and the terminal receipt records `last_task_result=0`, zero remaining instances, followed by task deletion. The task stdout identifies this exact run and manifest.

K15’s arena and room native runs both meet the 900-second minimum and exit naturally: the row records 927.453 s and 928.984 s, while the host results independently record 911.969 s and 914.468 s (both above 900), with lifecycle evidence and video verification.

## O13.3a same-run producer audit and O13.3b closure domains

The final runner derives nonce `1b5f2db09c` from this run ID and the frozen matrix closure. It creates the Blender content, registered roots, native fixture roots, both K8 publication roots, K6/K9/K10/K13 outputs, and K15 runs during the final task. The producer commands use those nonce-bound paths, and the producer implementations reject pre-existing output (`output.exists()` guards; K9 only permits a diagnostic resume, which was not used). The recorded root mtimes fall inside the Scheduled Task window (14:20:40–15:02:08), and each row references the exact generated paths and hashes. This establishes same-run producer membership; no historical publication was globbed or silently substituted.

O13.3b has two valid closure layers. The matrix closure covers the complete `studio/` source tree. Child runners hash their narrower declared source domains (for example, the content/publication/K9/K13 child closure `87718898b2e5c7a37a5d986567152afecda9ff20fe74c6b66aa71ccb6f6f9b2b`, and fixture-specific K15 closures). Those hashes are intentionally different from the full matrix closure and are checked by the child validators and row semantics; equality is neither required nor expected. The strict verify-only pass confirms the row closure bindings and all reference hashes.

## K9, K10, K13, and K15 requirements

K9 contains both arena and room real fixture faults observed in native Play, catalog repair batches with distinct command IDs, idempotent replay, durable reopen/checkpoint, and exit-0 receipts. K10’s conformance report is `CANDIDATE_PASS` with no errors and is bound to both final-run publication snapshots containing the lifecycle dependency; the current O13.1f rule makes the delegated K15 playtests sufficient, while human owner playtest remains explicitly non-required.

K13 is correctly fail-closed: the external adapter rows are measured, and the final client receipt is `MEASURED_INCOMPATIBLE` with concrete, measurable limits (the external route does not traverse HH lease/journal/semantic command-ID gates; raw warning/error logs are retained). O13.1e explicitly permits measured `INCOMPATIBLE` results with a reason and does not require an unsupported adapter to be relabeled `SUPPORTED`. The receipt binds the pinned external matrix, Codex/model provenance, both K8 recipe events, and both K9 repair events; no external compatibility claim is made.

No `OPEN`, `PENDING`, `DIAGNOSTIC`, or `CLIENT_OPEN` row remains in the final matrix. The package remains `authority=0`/`acceptance=false` as required before coordinator acceptance; this critic supplies the required independent `TICK=yes` only.

TICK=yes
