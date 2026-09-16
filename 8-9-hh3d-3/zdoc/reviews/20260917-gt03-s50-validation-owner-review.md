# S50 validation owner pre-freeze review

AUTHORITY=0. Bounded read-only source review, 2026-09-17. No tests, Docker or engine execution; no source edits or GT-03 acceptance signature. Findings refer only to the hashes below. Coordinator owns fixes and subsequent source freeze.

## P2: receipt release hash can describe transitive code that was not loaded

`studio/godot-addon/validation_owner.py:65-68` retains comparator, factory, codec and executor at module import. `ValidationOwner.__init__` snapshots disk release bytes later (197). `_healthy` (199-208) compares those disk bytes and three parent module identities, but not the retained codec/staging dependency identities.

Concrete sequence: import the module; change `bundle_v2.py` or retained `bundle_staging.py`; construct an owner; validate an eligible candidate using the retained codec. The constructor now attributes the new disk bytes to the release, while the previously loaded codec can still execute old bytes. Parent modules can remain unchanged, so the explicit loaded checks do not reject this. No malicious same-user memory patch is required; a normal source update between import and construction suffices.

Bind the actual transitive loaded-byte identities to the release manifest, or reject release changes since a trusted module-load baseline that covers these imports. Include a pure regression for dependency drift after module import but before owner construction, asserting rejection before executor invocation or receipt issuance. Receipt registration must never silently relabel earlier loaded dependency code.

## P2: probe constructor failures can skip retained native custody cleanup

`studio/tests/godot/run_components_probe.py:51` nests native construction inside the wrapper assignment. If `ProtectedFileRoot.create` fails with a retained `cleanup_owner`, or wrapping fails after native construction, `store` remains None. The finally block (101-110) then attempts `shutil.rmtree(parent)` without first adopting and closing that native owner.

Windows sharing may prevent deletion and cause another error, but that is not checked custody closure and may obscure the original ownership failure. Split native acquisition from wrapping, retain constructor `cleanup_owner`/`cleanup_api` as applicable, and delete only after every exact acquired owner closes successfully. Test native-constructor retained failure, wrapper-constructor failure and failed close; assert deletion is never attempted while ownership is unresolved.

## Other checked boundaries

`evaluate_run` is explicitly pure and cannot register a receipt. `validate` alone invokes the fixed executor, checks actual result/log files and comparison, then registers an exact receipt object. `observation` rejects copies/foreign issuers/changed bundle bytes and re-inventories retained evidence. Attempt count, cancellation hold and duplicate rejection are covered by the inspected pure tests. Those tests use a clearly marked executor double and are not native attribution proof.

The known caller-attested scene revision remains outside this review's findings. The probe and receipt keep `public_ack=False` and `selected_state_verified=False`; no active selector or public save authority is claimed. Successful source review would still require fresh same-closure native staging/validation/reopen evidence.

## Reviewed SHA-256

Paths relative to `8-9-hh3d-3/studio`:

| File | SHA-256 |
| --- | --- |
| godot-addon/validation_owner.py | c6df0f67315fca1610be9a37d74bdd57de2902ede6c824041a468406a4c76dca |
| tests/godot/test_validation_owner.py | 5c17b70bc4c31442c807623fcb225ffff8a63c08a36c845228810bdf0895f464 |
| tests/godot/run_components_probe.py | 88dc05a3a50e2fbe2773eca8a734cf77793f910ed4b5535cab55e656b3a63a5b |
