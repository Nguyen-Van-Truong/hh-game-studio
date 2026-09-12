# GT-01 TQ01 / TX12 / TX14 gap audit (read-only)

**Audit date:** 2026-09-12 (Asia/Saigon)  
**Scope:** S20 plan and `remint-s20/evidence.json`; this is an audit artifact only. It does not accept GT-01, alter a plan, or tick a work item.

## Inputs and integrity checks

- Current route is `GT-01`, `IN_PROGRESS`; the plan explicitly lists `GT01_PENDING=TQ01_TX12_TX14,TWO_CRITICS` (S20 plan, header and section 9.2).
- `remint-s20/evidence.json` reports `status=PARTIAL_RUNTIME_PASS`, `snapshot_matches=true`, `source_unchanged=true`, and explicitly limits itself to non-acceptance. Its 17-entry source manifest was recomputed against `studio/`; all 17 SHA-256 values match. Reproduction command: `python 8-9-hh3d-3/zdoc/reviews/20260911-r8/validate_s20.py` (observed `PASS_STATIC_ONLY`, 41 mutation tests, no failures; validator output itself says static-only).
- Remint lanes are version/import/parse/headless trace/menu quit/headed trace/headed menu quit/Blender save-reopen/Blender overwrite refusal. They all have host exit/tree/clean-stream fields; this is runtime smoke evidence, not the missing lifecycle or failure-injection coverage below.
- `critic-adjudication.json` contains only `SMALL_CHANGE_PASS` for critic A and `NO_VERDICT` (provider 403) for critic B; `GT01_ACCEPTED=false`. These are not two independent whole-WP critics.

## TQ01 — reproducible lock and fixture

**Requirement (plan):** Recreate lock and fixture under a path containing spaces/diacritics; stop before project open on checksum/version/OS/template mismatch; preserve old package; lock records Godot binary/templates/full commit, Blender/Python/addon/exporter, trusted scripts and supported host/target; clean environment must not depend on another PATH; committed lock/evidence contains no absolute path or username; another machine can reproduce from official URL + SHA without editing the lock.

**Evidence present:**

- `studio/toolchain.lock.json` is a `CANDIDATE` lock for Godot 4.7.2-stable, commit/tag, console+GUI SHA-256, archive SHA-256/SHA-512/size, export-template digest/size, Blender archive and executable digest, Python observed-only, and policy flags (`no_latest_autofetch`, `no_system_path_mutation`, `absolute_paths_forbidden`).
- S20 archive verifier/install tests exist (`studio/build/bootstrap/verify_archive.py`, `install_toolchain.py`, `tests/bootstrap/test_archive_and_install.py`). `REVIEW-RESULT.md` records offline ZIP verification and activate→rollback on an ignored `.local` root; remint records Blender save/reopen and overwrite refusal.
- Remint source closure is internally consistent (17/17 hashes above). `evidence.json` uses `$SNAPSHOT` placeholders in argv rather than leaking an absolute path.

**Missing / unproven:**

- No accepted evidence demonstrates a full clean-machine recreation on a root containing both a space and non-ASCII characters, including OS/host/target and export-template install checks. The remint ran from a snapshot but does not record that path-shape matrix or a clean PATH-independent environment proof.
- Export templates are explicitly `ARCHIVE_VERIFIED_NOT_INSTALLED`; therefore template availability/install is not proven. Python is `OBSERVED_ONLY`; addon/exporter/trusted-script inventory and supported host/target matrix are not evidenced as a complete manifest.
- Preservation of an existing package across reinstall/upgrade and “mismatch stops before project open” are not shown by remint lanes. No cross-machine reproduction artifact/receipt is present.

**Precise acceptance run:**

1. On a disposable host, set `PATH` to a minimal known directory and choose a product root such as `C:\Temp\HH Studio é\GT01 fixture`; do not edit the lock. Run the pinned archive verifier and installer with official URL/digests from `studio/toolchain.lock.json`; capture host exit, stdout/stderr, process tree, and package receipt.
2. Install export templates and run the fixture import/parse plus headed trace from that path. Record OS version, architecture, Godot observed version/commit, template digest, Blender/Python/addon/exporter versions, and supported target.
3. Seed an old package and sentinel asset, repeat install/activation, then inject each checksum/version/template mismatch. Acceptance requires refusal before project open, old package and sentinel byte hashes unchanged, no PATH mutation, no absolute path/username in committed evidence, and a second clean replay using the same lock with no file edits.
4. Recompute a complete closure manifest (including scripts, lock, templates/install receipts and test drivers) before runtime; post-run source hash must match.

**Stale/hash risks:** The remint’s 17-file manifest is current and matches, but it is a partial runtime closure; it does not include a template installation receipt or cross-machine matrix. Any source/lock/template change requires a new run ID, regenerated closure and fresh critics; do not reuse `20260912T131204Z`.

## TX12 — upgrade/downgrade/uninstall/ABI

**Requirement (plan):** GT-01 locks candidate/cache isolation; GT-08 covers ABI/template/build fixture; GT-10 is required for installer/migration/rollback/uninstall of the complete package. Copy project/cache in isolation, preserve old save/source, reject or reviewed-migrate incompatible schema, and uninstall must not delete assets. Never open an old editor on a new cache and delete on error; engine-core changes require ADR/owner.

**Evidence present:**

- `install_toolchain.py` and `test_archive_and_install.py` exercise package manifest closure, CAS state token, activation and rollback; the test suite passes these synthetic checks. S20 review records one offline install and activate→rollback trial under `.local`.
- Remint’s Blender overwrite-refusal lane demonstrates one protected-existing-file case; it is not an installer lifecycle test.

**Missing / unproven:**

- No Godot candidate A→B upgrade, B→A downgrade, incompatible schema rejection/migration, ABI/template compatibility, or uninstall run is present. No old-save/source sentinel and no cache-isolation proof are recorded.
- Synthetic activate/rollback is not complete-package migration/rollback; it does not prove editor/runtime behavior, asset preservation, or that an old editor cannot mutate a new cache. GT-08/GT-10 evidence is intentionally out of scope while GT-01 is open.

**Precise acceptance run:**

1. Build two immutable fixture packages from distinct pinned revisions (A and B), each with manifest/schema/ABI identifiers and sentinel project/save/assets. Install A into isolated cache/user-data roots; hash all sentinels.
2. Attempt A→B upgrade and B→A downgrade through the semantic installer. Exercise compatible migration and incompatible schema/ABI cases. Acceptance requires reviewed migration output with post-readback hash, or deterministic refusal before project open; original source/save and package A remain byte-identical.
3. Run rollback after a failed migration and verify CAS/transition journal, active package token, process exit/tree, and all sentinel hashes. Run uninstall and verify package metadata/tooling removal does not delete project assets or source.
4. Attempt opening an old editor against a new cache as a negative test; acceptance is refusal with no changed files. Capture full closure manifest and fresh source/binary/template hashes.

**Stale/hash risks:** Current lock is `status=CANDIDATE`; package tests are synthetic and their pass cannot be promoted to TX12. Any package or installer edit invalidates the remint source hash and requires a fresh full lifecycle run and two whole-WP critics.

## TX14 — quota/network/auth/token rotation/human Stop

**Requirement (plan):** Do not auto-switch model, read secrets, or retry paid work indefinitely; token rotation safely invalidates sessions; an in-flight command remains discoverable through journal lookup; user Stop does not auto-resume after reconnect; expose pending/gap/last-good clearly. Quota is not proof that source is wrong or a tool is permanently unavailable.

**Evidence present:**

- S20 process runner has bounded owned process groups, timeout/tree checks, clean-stream gates, and stop/leftover reporting for the lanes that actually ran. `run_fixture.py` and `install_toolchain.py` contain bounded process/CAS mechanics.
- Review narrative records worker rejects, a provider 403 for critic B, and memory trial with no permanent Codex/Grok config or hook. This supports “no bypass” as an observation, not a conformance proof.
- `evidence.json` limits explicitly call out bootstrap/reproducibility and independent critics as remaining work.

**Missing / unproven:**

- No fault-injection evidence for quota exhaustion, network loss/reconnect, auth failure, token rotation/invalidation, in-flight journal lookup, or human Stop followed by reconnect is present. No test proves no model fallback, no secret inheritance, bounded retry/backoff, or explicit pending/gap/last-good user output.
- The critic provider 403 is an observed no-verdict event, not TX14 acceptance. No paid-task retry accounting or quota telemetry is captured.

**Precise acceptance run:**

1. In an isolated fixture, inject quota=0, network disconnect at each phase, auth expiry, and token rotation. Run a command with a unique command/session ID and bounded retry budget. Acceptance requires no model switch, no secret values in stdout/stderr/evidence, finite retries with explicit terminal status, and old token/session rejection after rotation.
2. Stop during an in-flight command, terminate/reconnect the worker, then query the journal by command ID. Acceptance requires exactly one of committed result, explicit UNKNOWN/pending gap, or terminal failure; no duplicate mutation and no automatic resume after reconnect.
3. Capture human-readable `pending`, `gap`, and `last-good` fields plus host exit/process-tree proof. Repeat with a clean environment and inspect logs/evidence for tokens, usernames, absolute paths, and warning/error leakage.
4. Preserve the failed evidence and run a second independent replay from the frozen closure; acceptance requires matching source/lock hashes and bounded, explainable outcomes.

**Stale/hash risks:** Existing process checks cover normal completion and one overwrite refusal only. They cannot be relabeled as TX14 fault coverage. A new runner or journal implementation changes the source closure; mint a new run/command/session set and re-run all S20 gates before critic review.

## Recommended next sequence

1. Freeze a complete GT-01 closure and run the TQ01 path-shape/template/clean-environment matrix.
2. Run TX12 lifecycle/ABI/uninstall fixture with immutable A/B packages and sentinel hashes.
3. Run TX14 fault-injection and Stop/reconnect journal matrix with secret-redaction checks.
4. Generate one package containing raw logs, host exits, process-tree results, manifests and hashes for all three gaps; keep `PARTIAL_RUNTIME_PASS` evidence immutable.
5. Obtain two independent read-only Grok critics over that same frozen source hash. Only after explicit whole-WP `TICK=yes` verdicts may the coordinator consider GT-01 acceptance; GT-02 remains closed.
