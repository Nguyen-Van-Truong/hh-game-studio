# Atomic recovery inspection implementation review

Read-only cross-review after checkpoint `4eb8eee`, 2026-09-17.
This is an implementation review, not independent GT-03 acceptance.

Reviewed `studio/godot-addon/publication_recovery.py` SHA-256
`4ad678fc49826d4162ca8caac253bd4b8c50e6a6d9216cab9e5d6e35137b321d`
and the related inert inspection/planning/authority test changes.

The first reviewed patch (`dc1d2133c7279f3a9b6ef68d8f69450ea9dcb445b710c51e158c8d943d0d1b2d`)
had one actionable guard regression: the previous bind path called
`authority_context()`, which requires an exact `RecoveryJournal` owner.
The replacement `_inspection()` path initially lacked that exact-type
check. The coordinator restored `RECOVERY_JOURNAL_OWNER_REQUIRED` before
calling `inspect_command` and added the caller-dictionary/impostor rejection
test. The reviewed final hash includes that repair.

No further actionable correctness or security finding in this scoped diff:

- `inspect_command` holds the existing journal lock, performs a fresh
  `_refresh_view`, and derives command, snapshot, selected bytes and native
  head from that same verified pass.
- `_validate_view` retains the original native owners/custody/source checks,
  complete original and recovery replay, edit blob verification, head
  references, protected selector/bundle reads and alias checks. `_validate`
  still preserves the old tuple shape for existing append/open callers.
- The returned snapshot, command and context are copied through canonical
  serialization and parsing. The bundle itself is a frozen
  `CompleteFixtureBundle`; its file map is a copied `MappingProxyType` of
  immutable byte values. No mutable journal state is exposed by the view.
- No view is stored for reuse across calls or effects. Pre/post authority
  checks, live session/fence/deadline checks, actual content barriers,
  READBACK/TERMINAL append verification and live editor rereads remain.
- Inert tests cover next-call native failure, changed history/digest,
  detached return mutation and visibility of a later Stop/higher epoch.
  These tests do not replace native race, custody or engine evidence.

Remaining gate: new frozen crash-cut remint with actual process exits and
the unchanged 29-second reconcile request. The old `c354c978...` source and
its two held recovery attempts remain failure evidence and cannot be
relabelled as proof for this patch. No native process was launched for this
review.
