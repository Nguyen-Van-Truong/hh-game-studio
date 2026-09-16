# S51 draft JournalV2 integration review

AUTHORITY=0. Read-only implementation review, 2026-09-17. No engine/native
rerun, formal acceptance, source edits or plan tick in this review.
Reviewed draft `studio/godot-addon/publication_journal_v2.py` SHA256
`8e8c3daa3a85493eb678939ba98a8e6bd703f98c8871665346d2aa5b940f9ff7`,
with `tests/godot/test_publication_journal_v2.py`
`fccaa05ab93381b287ef11a058166ffe2274684440cdec3626bc64159f7e9e6e`
and frozen selector store `263e2253ee83f0ee9086159dc3aa9ab83843614751299f12bf5fec94090e2032`.

1. Reopen can accept a missing/replaced `active.json` at this draft.
   `_verify_bootstrap` compares the historical SELECTED version/hash to the
   recorded SELECTING bytes, but never compares them to the actual selector.
   A reopened store inventories the currently present namespace; if the
   selector disappeared while closed, all baseline bundle files can still
   verify and `_fold_verified` can return `bootstrap_bytes_verified=true`.
   `selected_bytes()` can subsequently return None. Require fresh native
   selector bytes/FileVersion equality to the latest durably owned selection;
   for this bootstrap/STAGED slice that is the bootstrap SELECTED record.
   Absence/change must hold. This is a direct code-path finding, not a claimed
   executed exploit or failure of the original create-time native barrier.

2. Some native store failures escape the sole journal cleanup owner.
   `prepare` calls store.prepare outside its poison catch; its cancellation
   error can also escape. `append` performs STAGED lookup/descriptor checks
   before its poison catch. A store verification failure on those paths can
   expose cleanup_owner=store and leave journal._held unset until a later call.
   Preserve ordinary pure/value rejection, but translate held/uncertain store
   errors to journal hold/cleanup ownership. Keep original BaseException
   semantics when cleanup also fails. stage_prepared already uses that pattern.

The draft correctly keeps one store/native close chain, journals planned names
before the twelve file writes, journals selector bytes before initial create,
and records the actual returned selector version before CONFIG. Source-bound
replay never executes or rearms. The store's exact registered selection API is
compatible. The ordinary publication owner and live lease/Stop/engine guard
integration remain unavailable; caller-supplied validation events are still
attestations, with no public ACK granted. Both findings were sent to the root
implementer for correction; this report binds the reviewed draft, not any later
fix or acceptance claim.
