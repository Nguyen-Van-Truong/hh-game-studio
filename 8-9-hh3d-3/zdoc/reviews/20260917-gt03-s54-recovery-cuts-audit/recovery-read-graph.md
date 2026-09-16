# Recovery read graph and bounded refactor proposal

Read-only analysis of frozen runtime `c354c978062dc9987f98eae28d5af158bed5256ba25126457be44d43a720150f`.
No runtime edit, performance acceptance, or deadline change is proposed here.
Line numbers refer to that package's `source/studio/godot-addon/publication_recovery.py`.

## Current read graph

`RecoveryJournal._refresh()` (line 670) performs owner/custody checks,
`_read_unbound()` (line 623: complete `PrivateEventLog.fold`), and
`_validate()` (line 637: original V4/V5 publication replay, edit blob
verification, complete recovery-tail fold, native head-reference checks,
selected descriptor and bundle read). It verifies the complete `_events`
tuple against the observed stream. This is a complete fresh trust-boundary
check, not a cheap in-memory snapshot accessor.

`PublicationRecovery._view()` (line 126) does four complete refreshes:

1. `_snapshot()` → journal `snapshot()` → `_refresh()`.
2. Journal `lookup(command, digest)` → `_refresh()`.
3. Journal `read_selected_bundle()` → `_refresh()` and another descriptor read.
4. Journal `selection_facts()` → `_refresh()`.

The four results are checked for agreement, but their underlying native
reads are separate. `observation()` calls `_view()` and then performs a live
editor readback. `observe()` in `reconcile()` calls `_view()` before and after
fresh editor construction.

`ReconciliationAuthority.bind()` (line 835) does three complete refreshes:
owner `authority_context()`, journal `snapshot()`, and journal `lookup()`.
It validates Stop/held/command state and higher fencing against these reads.

Each authority `_phase()` does a fresh `authority_context()` before its
effect and another after it. Every pre-phase guard also rechecks the live
registered session/lease/deadline. These are effect boundaries and must
remain independent fresh checks.

The complete success path before editor construction has **12 calls to
`_refresh()` plus one direct post-append full fold/validate = 13 complete
fold/validate passes**:

| Operation | Complete passes |
|---|---:|
| Authority bind (context, snapshot, lookup) | 3 |
| Capture phase precheck | 1 |
| Admit initial refresh | 1 |
| Admit append precheck plus post-append validation | 2 |
| Capture phase postcheck | 1 |
| Adopt phase precheck | 1 |
| Observe initial `_view()` | 4 |
| Total before editor construction | 13 |

`admit()` also reads and reapplies **13 actual native content barriers**:
the 11 bundle files, manifest and selector. Those are intentional durable
publication barriers, not redundant read-only checks to remove. The observed
20.796-second request-to-editor interval includes both replay/check costs
and these barriers; the existing evidence does not separate their durations.

After editor construction, the successful path performs another `_view()`
(4), adopt postcheck (1), commit precheck (1), two `observation()` calls
(4 each), a selected snapshot (1), READBACK append (2), TERMINAL initial
refresh plus append (3), recovered response read (1), commit postcheck (1)
and host terminal read (1). Thus the ordinary reconcile path up to the host's
terminal response performs **36 full fold/validate passes**. This static
count excludes HTTP lookup/lease setup, harness assertions, constructor/open
checks, error handling, retries and nested lower-level storage validation.
The failed continuation reached the live commit precheck after the first
18 passes; `_check_live()` then rejected expiry before that phase's native
context refresh.

## Smallest safe consolidation

Introduce a **journal-owned atomic inspection method** under one existing
`_locked()` scope. It performs one `_refresh()`, then derives detached
snapshot, command/digest result, authority context and selection facts from
the same returned `(publication, recovery, selected)` objects and exact
`self._head`. A command-specific view optionally returns the exact complete
bundle read during `_validate()`. Refactor `_validate()` internally to retain
that already-verified bundle for this immediate return; do not persist it as
a trusted cache across effects or calls.

`PublicationRecovery._view()` can use one atomic inspection instead of four
refreshes, retaining all source/readonly/command/manifest/selector equality
checks. `ReconciliationAuthority.bind()` can use one atomic inspection
instead of three, retaining the existing live grant/deadline check and
higher-fence/Stop/held checks. This removes repeat work within a single
logical observation while making the values coherent under one journal
lock. It does not skip a native verification boundary.

Do not accept caller-provided snapshot dictionaries as authority. Avoid a
generic optional `skip_verify` parameter. Do not cache across editor I/O,
append, custody movement, Stop/revocation, or selector changes. Keep all
pre-effect and post-effect authority context refreshes, the live editor
rechecks before terminal, original/recovered exact-response distinction,
edit blob checks, V5 replay, native barriers, and post-append verification.
Keep the 30-second recovery cap and existing higher-fence rules unchanged.

The minimal change saves **14 of 36** complete passes in the static success
path: two in bind and three in each of four `_view()` calls. It saves five
of the 13 passes before editor startup. The explicit selected snapshot
inside completion could later be derived from the same immediate
observation, but is not needed for the first minimal refactor.

## Verification if the quiet run confirms a budget problem

- Verify command/digest conflicts, source mismatch, Stop, held recovery and
  fresh fencing still fail at the same boundary without creating an editor.
- Use meaningful tamper tests: change native selected bytes, custody/head,
  original/recovery event data or edit blob between observations and verify
  the next atomic inspection rejects them; never reuse an earlier snapshot.
- Verify all returned views derive from one head and do not expose mutable
  internal publication/recovery objects to callers.
- Preserve existing authority phase-order, Stop latency and native-head
  corruption regressions; test exact original/recovered response bytes.
- Mint a new frozen source closure after any runtime edit and run the affected
  actual crash/recovery chain with real process exits and an unchanged 29s
  request. Old storage's registered source closure cannot be relabelled as
  the new runtime; any continued old-runtime proof remains separate.

This proposal needs runtime-owner implementation and review. A quiet retry
is still required before concluding that the measured failure is an
algorithmic budget issue rather than contention.
