# S52 next: bounded same-app reconciliation

AUTHORITY=0. Read-only review; no source changes, engine runs or acceptance claim.
Basis: plan §2.2/2.3/2.5/2.6, GT-03, TQ02/TQ03/TQ07; current Godot owner,
journal/session/store; accepted ManagedFixtureOwner, ProtectedFileRoot/EventLog.

**Recommendation:** recover on the original storage ID/roots/event chain. Keep
native project files read-only, but allow narrowly verified recovery/terminal
journal facts under original custody. A fresh actual editor loads and reads back
the complete selected bundle. This can complete a pending save or restore the
unchanged last-good editor state without enabling another native publication.
Generic recovered writable publishing is not a prerequisite for every GT-03 result;
merely opening a readonly snapshot also does not prove required complete/restore.
GT-03 still needs scene+script crash/response-loss recovery; GT-07 expands scheduling.

## Proven primitives and gaps

- JournalV3 checks custody, native identities, the full fold, selector FileVersion
  and all twelve selected objects. Its ordinary reopen remains permanently readonly.
- Accepted `ProtectedFileRoot.confirm_barrier` works on reopened readonly roots and
  rechecks/flushes file plus directory. `PrivateEventLog.reopen/append` can append to
  the original stream with head comparison, flush/readback and custody persistence.
  A separate typed recovery journal can use these unchanged primitives. Do not
  silently weaken ordinary v3 reopen or its mismatch rejection.
- V3 READBACK binds the original editor session; UNKNOWN holds normal transitions.
  Fresh recovery needs explicit recovered-editor events, never copied old identities.
- **Idle Stop after COMMITTED is currently memory-only.** Stop during save becomes
  durable UNKNOWN, but a terminal-only restart could forget idle Stop. Persist verified
  Stop/control intent before enabling recovered terminal completion.
- `_jobs`/public responses and lease issuance are memory-only. Historical lookup and
  dedupe must come from durable history; resetting them is not recovery.

## Concrete bounded API path

1. `RecoveryJournal.open(storage_id, project_id)` retains the original exclusive
   guard, verifies custody/stream and a versioned typed publication+recovery fold.
   `inspect(command_id,digest)` classifies actual selector bytes/version against
   last-good and the one durable activation intent. No request paths or rearm flags.
2. `GodotReconciliationOwner.open(...)` creates a fresh, bounded `control.reconcile`
   issuer and records a unique recovery epoch/admission binding the original command,
   custody head, descriptor and exact compatible source/pins. Old bearer/lease/permit
   rejects. Ordinary scene.save remains disabled; no recovered native writer.
3. `reconcile(command_id,digest)` reads all eleven inputs plus manifest, applies a
   fresh native barrier, materializes a new owned editor mirror and launches actual
   EditorOwner. Compare exact full semantic JCS, all inputs and scripts. Bind new PID
   **and creation identity**, session/root/generation, source and engine pin. Preserve
   candidate/checkpoint bytes; never restore old ObjectIDs, UndoRedo or credentials.
4. Append typed `RECOVERY_ADMITTED`, optional `RECOVERED_SELECTION`,
   `RECOVERED_READBACK`, `RECOVERED_TERMINAL`, linked to the original command/digest,
   prior event head and issuer-registered observations. Only the recovery owner may
   issue these facts. Original publication prefix and dedupe ledger remain unchanged.
   No native file publication occurs. Terminal/custody failure remains UNKNOWN; ACK
   follows durable terminal readback, never an editor message alone.
5. Persist original public response bytes (or an exact versioned deterministic
   representation) before delivery. New authenticated lookup returns those historical
   bytes without replay; pure `public_ack=false` records are not relabeled. Keep the
   original response generation distinct from the fresh recovery editor identity.

| Durable history / actual native state | Required recovery and outcome |
|---|---|
| COMMITTED; exact complete selection | Fresh editor readback; original terminal lookup, no replay |
| SELECTED; exact candidate; no Stop/UNKNOWN | Barrier + fresh editor readback + recovered terminal; complete only this save |
| ACTIVATING; selector still exact old last-good | Load/readback last-good in new editor, preserve candidate; explicit recovered failure/restoration |
| ACTIVATING; exact durable candidate intent selected, SELECTED witness missing | New strict recovery classification, barrier, recovered selection fact and fresh editor readback before terminal |
| Stop/UNKNOWN, arbitrary mismatch, orphan or custody ambiguity | Inspect/preserve only; no automatic replay or terminal success |

The third row restores editor state while the native last-good selector never changed;
it does not claim a rollback write. The fourth row needs a distinct strict reader:
current v3 correctly rejects it. Keep that gap if unimplemented. Rollback requiring
selector replacement remains outside this slice; readonly inspection alone cannot
claim it. Scene+script crash coverage remains required as script replacement lands.

## Stop and subsequent writable restart

Keep the immediate Stop latch independent of engine work. Add a separately owned
restart-stop fence/control persistence lane; distinguish latch, draining and durable
confirmation. Confirmed Stop follows its barrier; failed/pending persistence is
unconfirmed/UNKNOWN. A message lost before any durable record is not reconstructible.
Persisted or ambiguous Stop/control history denies recovery completion/publication.

For **new publishes after restart**, separately prove terminal-only admission, fresh
**durable** fence/lease authority, complete finite native inventory and a genuine
bundle-specific rearm primitive. GT-02 rearm only accepts its registered inert
consumer and namespace `.writer` + `active.json`; Godot obj-* files cannot use it.
Do not spoof `_fixture_file_consumer`, flip readonly flags or clone/reset the ledger.
Any native-boundary extension needs explicit plan scope/regression/review; the
reconciliation API above requires no accepted GT-02 changes.

## Focused actual tests

- COMMITTED/lost HTTP response → owned-host death → same storage/custody/stream,
  new actual editor readback and byte-identical lookup/retry, no repeated effects.
- Crash SELECTED→READBACK; crash before CAS; crash after CAS before SELECTED: exercise
  the table's exact completion/restoration, with complete scene/script hashes.
- Old auth/lease/permit rejects; simultaneous recovery uses the same exclusive guard.
  Changed native IDs, aliases, missing/extra objects, source/pin and custody skew reject.
- Idle Stop after COMMITTED, Stop during validation and control-persistence failure:
  no forgotten Stop, fabricated durable confirmation or auto-resumed UNKNOWN.
- Crash after recovery admission/readback/during terminal custody: same-chain replay,
  no duplicate effects, retained cleanup and actual exit/tree evidence.

Serialize native Linux validation lanes: admission maximum is one. Happy04+Stop01
produced EXECUTOR_ADMISSION_BUSY, an orchestration collision; preserve it and resume
the unfinished lane without weakening the accepted boundary.
