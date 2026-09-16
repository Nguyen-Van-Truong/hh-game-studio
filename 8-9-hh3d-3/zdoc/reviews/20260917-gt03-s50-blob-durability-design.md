# S50 complete-bundle namespace barrier design

AUTHORITY=0. Read-only source/document review, 2026-09-17. No native probe, source change, acceptance, plan tick or power-loss experiment.

## Finding

A directory barrier cannot be bolted onto the live **PrivateBlobStore** with its current handle sharing. An addon-owned complete-bundle backend can instead reuse the exact existing **ProtectedFileRoot.create_new/read/confirm_barrier** APIs, without modifying or copying GT-02 native code. This is a proposed integration, not evidence that GT-03 already has durable staging or selection.

Use the journal's already provisioned `files` root for twelve generated flat immutable names plus the separate selector. Keep the private blob root as the existing custody resource; do not pretend its identity identifies those content files. A versioned addon descriptor/state binding and one lifecycle owner are required.

## Existing gap and handle facts

* `studio/godot-addon/bundle_staging.py:206-263` reserves eleven profile files plus one manifest, performs actual puts, complete-set readback/decode and inventory comparison. Its receipt deliberately fixes `namespace_durability_verified=False` (line 78).
* `studio/host/core/private_store.py:173-187,257-276` retains ancestor/root directory handles with `FILE_LIST_DIRECTORY|FILE_READ_ATTRIBUTES|READ_CONTROL`, share **READ only**, `OPEN_REPARSE_POINT|BACKUP_SEMANTICS`. The root handle lacks GENERIC_WRITE. Reopen additionally retains the root through the ancestor list.
* Its `put_bytes` (358-392) uses write-through, checked write count, checked file `FlushFileBuffers`, handle identity/security and byte readback, followed by checked close. No root/parent directory flush is exposed. Do not describe this as zero metadata flushing: Microsoft documents NTFS metadata effects of write-through.
* A fresh GENERIC_WRITE root handle conflicts with the retained share-READ handles. Preopening the writable handle reverses the same sharing conflict. Closing/replacing retained core handles would change the custody/ancestor protection and cleanup ownership; that is not a safe addon barrier implementation.
* `safe_create.py:133-145` also needs a new writable directory handle, so it does not bypass this conflict. Borrowing a different root's successful flush proves nothing about these twelve names.

Microsoft requires GENERIC_WRITE for `FlushFileBuffers`; a volume-wide flush requires administrative privileges. Neither a read handle nor an assumed privilege supplies this barrier. [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)

Sharing constraints apply to existing and new opens until handles close. BACKUP_SEMANTICS permits a directory handle; privilege overrides require actual backup/restore privileges. WRITE_THROUGH has documented NTFS metadata effects, but hardware support is conditional. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)

## Reusable checked path

1. `safe_replace.py:118-146` retains immediate parent/root with share **READ|WRITE**, without DELETE sharing. Earlier ancestors remain share READ. New-root creation checks local NTFS, owner DACL and guard, flushes the guard, flushes the root, then its parent. No elevation or privilege adjustment is added by these methods.
2. `create_new(name, bytes)` / `_put` (312-388) creates a private temporary, checks bytes/identity, performs checked rename, verifies final-name identity/bytes, and calls the checked root-directory barrier after publication. Successful return also passes the checked operation closes. This is stronger than substituting a file-only flush.
3. `_ReplaceApi.flush_directory` (81-90) opens that exact directory using GENERIC_WRITE plus list/read-attributes/READ_CONTROL, share READ|WRITE, OPEN_EXISTING, no-follow and directory flags. It checks volume/file ID against the retained identity, final path/type/reparse state through `inspect`, protected DACL for the root, native flush result and checked close.
4. `read` returns `FileVersion(FileIdentity(volume, file_id, size), sha256)` with actual bytes and checks before/after. `safe_open.py:113-137` also rejects reparse points, wrong type, delete-pending files, multiple hard links, nonlocal/final-path aliases.
5. `confirm_barrier(name, expected_version)` (261-284) opens the known file for flush, checks its complete version, flushes it and the root, rechecks version and retained owner state, and checks close. It holds/poisons on uncertain barrier effects. It does not select, ACK, clear read-only state or authorize replay.

The directory call is an existing checked local NTFS primitive. The cited Windows contract and normal process tests do not prove arbitrary storage hardware survives physical power loss. Report native barrier completion and its tested filesystem scope, not a universal power-loss guarantee.

## Concrete addon transaction and lock order

* One publication lifecycle owner owns the **same exact** `ProtectedFileRoot`; no second stager independently wraps a journal-owned resource. Order: bounded publication RLock acquisition -> native file-owner mutex inside each public call -> release native mutex before journal/custody/log calls. Never hold `files._mutex` while calling `read/create_new/confirm_barrier`: it is non-reentrant. No callbacks from native owners into the publication owner.
* Under that lifecycle lock, validate the exact v2 bundle and reserve the complete twelve-file count/bytes plus selector capacity. Inventory names only by enumeration, then obtain every identity/size/DACL through checked native handles; include unrelated/orphan files and previous versions.
* Mint twelve distinct lowercase owner-generated names, e.g. `obj-<uuid32>`, mapped to the eleven fixed logical profile paths and `@manifest`. Never pass bundle paths such as `addons/...` to the flat store. Only the separately reserved fixed selector name may use `atomic_replace`; immutable content gets `create_new` only.
* Register intent, names and attempted effects before each call. Retain each exact returned `FileVersion` immediately. Write all eleven content files, then the manifest last. Native failures retain partial/unknown ownership and reservations; no implicit retry/delete/reuse.
* Read all twelve exact names; compare returned FileVersions, byte counts/hashes, original bytes and decoded manifest. Check resulting complete inventory against baseline plus precisely twelve new identities.
* Call **`files.confirm_barrier(manifest_name, manifest_version)` only after the complete-set check**, then re-read all twelve and recheck inventory/root custody under the same outer lock. Earlier successful `create_new` calls already provided individual post-rename root barriers; the final manifest call supplies an explicit batch-end root barrier.
* Register an internal barrier record only after every native call and close succeeds. Bind root volume/file ID, all twelve names/FileVersions, manifest/project digest, command ID and exact lifecycle-owner identity. Accept only the actually registered object; reject copied receipts, caller booleans/callbacks and synthetic versions. A durable journal reference must carry those descriptors and be independently reread before future selection.
* A held/closed owner or subsequent uncertain mutation invalidates advancement. Selection may consume the registered record only with fresh owner/current-base checks. Engine eligibility/readback and terminal journal/selector barriers remain independent requirements; `public_ack=False` remains mandatory here.

## Integration limits that matter

* Core limits are **1 MiB/file, 64 names, 8 MiB aggregate** (`safe_create.py:25`, `safe_replace.py:32-33,293-310`). V2 has eleven files, a <=16 KiB manifest, <=2 MiB content, and no individual file over 1 MiB (`bundle_v2.py:16-32`). Reserve actual manifest bytes too.
* The core quota runs before both create and replace and rejects an existing count of 64. Leave count headroom for selector replacement; reserve the selector's incoming bytes conservatively because replacement quota includes the old value. Account for transient staging bytes as well. Do not equate twelve successful puts with safe capacity for publication.
* `_path` (227-235) permits a flat nondot name only, with SafePathResolver validation. Generated names should have a tighter exact regex and a disjoint selector name; logical profile paths remain manifest data.
* **Provisioning order matters:** `PublicationJournal.create` creates `files` before `blobs` and `events` (106-108). Their later share-READ parent handles can block a new sibling file-root constructor's parent flush. Reusing the existing files root avoids this. Do not lazily create another sibling backend after those stores are live.
* `WitnessCustody` binds three distinct root paths/identities, not their content inventory (`custody.py:82-102,190-200`). An unused-but-owned private blob root can remain for this contract; it still requires normal guard/identity checks and close ownership.
* Current publication CONFIG/replay/append explicitly bind `store_identity` to `_blobs` (`publication_journal.py:116,216,238`), and v1 state descriptors describe its blob model. A new addon schema must explicitly bind complete content to custody's **files** root and FileVersions. Do not relabel old StagedBlob descriptors or silently reinterpret an existing journal.
* Fresh file roots can mutate. `reopen_readonly` permits read and `confirm_barrier`, but not new staging/selector writes. The existing `_rearm_verified_snapshot` only accepts the fixed inert `active.json` namespace. Twelve extra names do not fit it; GT-03 restart write authority remains unimplemented. Do not set `_readonly=False` or forge the inert-consumer marker.

## Proposed focused native tests after freeze

1. Actual local NTFS root: stage twelve unique names, capture native file/root identity and checked call results, confirm manifest barrier, close/reopen read-only and reread all twelve. Verify parent/root/guard protection and no retained failed handles. Existing `test_safe_replace.py:241-254` covers known-value confirmation without rearm, not the new batch.
2. Sharing negative: with live PrivateBlobStore, attempt only its exact root writable-directory open and record native sharing failure; show no success receipt. Separately prove file-root barriers still work with the later private/event siblings alive. Test prohibited late sibling-root provisioning without treating constructor leftovers as success.
3. Inject failure at each file flush, pre/post-rename root flush, final manifest flush/root flush, identity/DACL check and close. Require no barrier record/selection, retained cleanup owner, full reservation and no automatic replay. Include a final-barrier callback that merely returns success: it cannot supply native evidence.
4. Wrong root/FileVersion/name/hash, copied receipt, missing/tampered twelfth file, unexpected orphan/extra name, quota boundary with selector reserve, traversal/ADS/reparse/hardlink, and parallel staging/close must reject or hold before advancement as appropriate.
5. Kill an owned test helper at bounded stage/manifest/final-barrier cuts; reopen and reconcile actual names/descriptors while remaining read-only. This proves process-crash behavior only. A power-loss claim would need a separately authorized controlled storage/power-fault experiment.

## Read snapshot SHA-256

Paths below are relative to `8-9-hh3d-3/studio`; these identify reviewed bytes, not a frozen integration release.

| File | SHA-256 |
| --- | --- |
| host/core/private_store.py | c914b5a66a45660c782ecd43fd2321c238702340f3b33062e284feada4d46476 |
| host/core/safe_replace.py | 369459bb5fca4ebaf11a4ce9ac848024a9f63502a0df4bbe68d5aa585e2e3fb9 |
| host/core/safe_open.py | efc083f1c4fa875d3f748602924a05712aa60fed3abcdb46d058672930201535 |
| host/core/safe_create.py | 681fb7c0f4e74d82597bd8049a6b42cde0ea73941d879ec8ef0ba4df326d0606 |
| host/core/custody.py | aa4320faeccb3b729d0eebf29ac3e962d2590bca1e3aba14b0aef620b021fbc9 |
| godot-addon/bundle_staging.py | 3d614edbec8e9a7f5ad3caf2b9694d7498df129de95683952268621f91d68e43 |
| godot-addon/bundle_v2.py | 2c5cdc71cdaf80f58bb93ec791e84bab8bd02cd4d9bdbd93d635db13583de62a |
| godot-addon/publication_journal.py | aa230fc6f31bec6ae69c7192cba92bbd6438cf00a4a0680fd2ce26f55cd02f23 |
| tests/protocol/test_safe_replace.py | 95a0cd3d0b17af8cb81ecd0c1f43e49e5e0eb764a70460d507a911b1c2d05b60 |
