# Blender client transport component cross-review

Date: 2026-09-17, Asia/Saigon. AUTHORITY=0. FORMAL_ACCEPTANCE=0.
Baseline Git HEAD: `4eb8eee5bb2213af981155648508a058f54fc448`.
This is a bounded implementation cross-review, not either final acceptance critic.

Later frozen native attempts are audited in
`../20260917-gt04-client-audit/README.md`: attempts 01/02/03 remain FAIL;
attempt04 supplies the successful read-only native client component at its own
new source closure. Its integration found and fixed the native unleased-inspect
after writer-fence issue; the earlier read-only source review below is historical
and does not stand in for that runtime evidence.

## Scope and observed verification

Reviewed `client_transport.py`, its companion tests, the public owner/session/catalog
interface and coordinator-owned `run_client_probe.py`. No native engine, journal,
storage lane, core/platform/plan or Git mutation was run. Active process inventory
at entry showed no Godot or Blender process. Other working-tree changes predated
this review and were not included or reverted.

Only `studio/tests/blender/test_client_transport.py` was changed. Two tests add:

- Real production `BlenderClientSession` over actual loopback sockets with an
  explicit inert backend. Empty fixture scopes work through all three listeners;
  a raw issuer-only fixture token has no registered Blender grant; rotation
  invalidates the old bearer; canonical Stop uses the same Blender authority.
- Malformed owner output (NaN, cyclic object, unsupported object) and unexpected
  exceptions containing a credential are bounded/redacted, release historical
  lookup admission, and permit a subsequent valid lookup.

Existing 24 socket tests passed before additions (6.470 seconds). Expanded suite
passed 26/26 (6.802 seconds), actual subprocess exit 0, under a 45-second outer
subprocess timeout. Reproduction from repository root:

```powershell
python -B -m unittest discover -s 8-9-hh3d-3/studio/tests/blender -p test_client_transport.py -v
```

These are live checkout component results, not a frozen full-runtime source
closure or Blender readback proof. Coordinator must verify its final frozen
closure independently. Component hashes observed after the test run:

| File | SHA256 |
| --- | --- |
| `studio/host/blender/client_transport.py` | `8a4389097e27460cbad0d293dbc0da6b9b25acd6b4679ea295eae2b16300a2d4` |
| `studio/tests/blender/test_client_transport.py` | `3b3bc9c2462f9d9bc50d69441f4e9c31928b785bbb4c6c7fffc3be0d45ac5a0e` |

No production transport correction was needed. Reader/writer delegation is exact;
Host is narrowed to the actual listener; canonical Stop has its own connection
slots; lookup has one reservation held through response send; errors/disconnects
release it; failed startup and incomplete drain retain the exact transport owner.
Its claims exclude saturation of the Stop listener itself and OS scheduling.

## Cross-component findings sent to the assigned writers

1. The owner's final read authorization check and response cache publication had
   a gap in which Stop/revoke could overtake publication. The facade writer added
   a session publication guard, with no native wait inside the guard.
2. An unexpected final Job query exception could leave `_active` and a pending
   command stranded. An unexpected `host.stop()` exception could leave
   `_stop_pending` stranded. The facade writer moved final construction and
   native rechecks inside terminal error handling and handles unexpected Stop
   errors as bounded UNKNOWN outcomes. Their added regressions remain owned by
   that writer and require final source verification.
3. The probe assigned `server = BlenderClientTransport(owner).start()`, losing
   its local handle when startup reported retained cleanup. It also closed the
   native owner after transport drain failure. Coordinator separated construction
   from startup and added Stop/drain retry while retaining GUI ownership. A
   follow-up noted that `BlenderUIHost.__init__` can itself attach a retained
   `cleanup_owner` to its exception; coordinator now retains that exact owner
   when constructor assignment never completes.
4. Owner observation hashing preceded transport redaction. Native object and mesh
   names are emitted by the adapter without a path-text restriction. A name such
   as `C:/private/item` can be changed to `[HOST_PATH]` by the accepted core output
   encoder, leaving a COMMITTED result hash inconsistent with its received
   `jcs-observation-v1` preimage. This was sent to the facade writer before freeze.
   A pure boundary reproduction, with no native launch, observed claimed hash
   `sha256:a32a1c3dbd02ca28cf376168551eedce63c76b5caeed9e6ed1a1683a4a3c3ae5`
   versus received-observation hash
   `sha256:0e0f5fa0ec84d1b6b6767e3b5a92cba4faa1bc3b56f99118f3635539a6a8d55e`.
   This is a boundary counterexample, not evidence of native execution. The
   facade writer has chosen to reject any redaction-changing COMMITTED read
   before publication and recheck at the actual session output boundary,
   including later secret-history expansion. The final read-only follow-up below
   confirms that implementation is present; the counterexample remains useful
   historical evidence of why the guard is needed.

The bounded transport slice has no remaining finding from this pass. Final
native cleanup, exact response/hash and independent same-source critic
requirements remain with coordinator. No acceptance tick is issued here.

## Final read-only probe and facade follow-up

Reviewed final files, without executing them or modifying runtime/probe source:

| File | SHA256 |
| --- | --- |
| `studio/tests/blender/run_client_probe.py` | `5d14ab998b5e9250bd43a7225719b65d10f1eef6eb729175411f118e3918f6ff` |
| `studio/host/blender/client_owner.py` | `a4be370b8521d32c215bddd2ebf58b4facd0c0ac7b08abc74173106dd9c472bc` |
| `studio/host/blender/client_session.py` | `6997d7dc916ea33265cadaa71c5d811b6b7c9d3710e073c4b8a6921cf6e7710b` |

No remaining scoped probe/API finding. The probe uses actual common
Discovery/Request/Response types and matches the final exact method envelopes.
Discovery binds project/catalog/server/source; the read response binds command,
revision, source, native PID/generation, scene/context and the JCS observation
hash. Duplicate and own-session lookup compare raw bytes; another session cannot
obtain that receipt. Unsupported mutation, bad catalog, revoked bearer and stale
revision cannot count as the single new native data read. Stop uses its dedicated
listener and subsequent discovery/lookup matches the stopped-owner contract.

The simple box fixture contains no redaction-changing names and issues all three
credentials before observation, so its exact-wire assertions fit the new guard.
Owner publication rejects changed encoded bytes; the session output boundary
repeats this for historical responses after credential history expands. It denies
delivery instead of changing an observation under its original hash.

Constructor-retained GUI owners are captured; transport construction precedes
startup assignment; drain failure retries Stop/drain before native owner release.
Successful native/child exits and cleanup are assertions to be observed by the
coordinator's run, not outcomes asserted by this read-only review. No new tests,
native processes, journal/storage operations or acceptance verdict were run here.

## GT04 public write and recovery gap map

This map follows the authoritative tools plan S55, section 2.2 (common adapter
contract), section 2.3 (Blender/Stop), section 2.6 (mutation preview/recovery),
GT04, TQ04 and TX02/03/04/05/06. Section 2.2 explicitly requires baseline safety
at the first GT03/GT04 mutation; GT07 extends it. Historical component audit
maps provide context only and cannot add a mandatory gate to that plan.

| Area | Existing source and limit | Required next boundary |
| --- | --- | --- |
| Client write contract — GT04 | `client_catalog` exposes only `scene.inspect`; facade has only read leases. Native create/transform/material/UndoRedo/save/export exist behind trusted direct objects. | Expose the supported GT04 create/typed-transform/save/checkpoint/export set through reviewed common capabilities, Request/Response and authenticated Blender-specific write grants. Explicit unsupported operations remain valid; read-only completion alone cannot close GT04 BUILD. |
| Writer safety — GT04 baseline/TX06 | `DurableBlenderSession` and `BlenderWriterJournal` provide internal FIFO, lease/fence, native admission and Stop. A public Blender session currently has no relationship to this writer. | Register the exact native host, durable session and public writer grant together. Bind client identity/project/target/operation, lease ID/fence, expected revision/context and absolute deadline; recheck before native effect. Fixture scopes or caller-supplied paths/PIDs/lease-shaped objects are not registration. |
| Public duplicate and timeout lookup — GT04 baseline from section 2.2/GT02 | Read facade stores 32 volatile records. Internal durable receipts use `HH-BLENDER-DURABLE-RESPONSE-1`, private command digests, `public_ack=false`, `scene_state_durable=false`. | Persist the common Request identity/digest to private command translation before dispatch, and the exact public terminal Response before ACK. Preserve conflict/UNKNOWN/tombstone behavior across the declared retry horizon; a reopened historical lookup must not execute an unresolved command. A private receipt cannot simply be relabeled as a new public result. |
| Save/checkpoint/export and reopen — GT04/TQ04 | `ui_host` owns fixed paths and native readback. UI checkpoint save explicitly says `durable_publication=false`. `BlenderPublicationOwner` can protect one complete checkpoint/GLB/manifest and selector with barriers. `CheckpointRecoveryOwner` verifies a fresh read-only GUI after the exact clean predecessor closes. | Bind advertised save/export requests to those artifact identities and native readbacks, with explicit persistence semantics. Reopen must verify mesh/transform/material on the final source. A live edit can declare live scene state; a durable response does not make unsaved GUI state durable. Neither internal native save nor exit0 alone proves durable source publication. |
| Supported recovery policy — GT04 baseline | Unresolved private intents return UNKNOWN; publication reopening is read-only; fresh checkpoint recovery requires a clean closed exact predecessor and grants no writer. | Document and preserve these limits. Required duplicate/timeout handling, safe Stop/cleanup and the supported checkpoint reopen must be externally understandable. Do not replay unresolved effects or overwrite manual edits. TQ04 does not itself require a writable restart, old Undo history restoration, reconstruction of an arbitrary crashed GUI, or a new durable recovery command. |
| Input closure — GT04/TQ04/TX04 | Current publication allows original fixture inputs only, `external_inputs=[]`; unsupported libraries/textures/drivers/addons are rejected. | Keep that explicit catalog boundary. If linked libraries/textures become supported, materialize copies under staged root with identity/hash/license/relative mapping before import/publication; a hash of an external path is insufficient. No arbitrary `.blend` intake is opened by a writer grant. |
| Broader recovery and activation — GT07 (after GT05/06) | No cross-app active editor release, writable generation adoption, full interrupted publication reconciliation or multi-agent scheduler across Blender/Godot. | GT07 owns dependency/FIFO/fairness at that scope, two-app activation, crash at every publish/reload/ACK phase, restart reconciliation, last-good selection and rollback that preserves newer manual edits. Do not require GT07 completion before accepting the narrower GT04 contract, and do not use that deferral to omit initial lease/revision/dedupe/checkpoint/Stop safety. |

The current GUI checkpoint consumer is therefore useful TQ04 reopen evidence
within its stated clean-predecessor scope. Its flags (`recovery_durable=false`,
`new_edit_grant=false`, `undo_history_restored=false`, `public_ack=false`) are
accurate limitations, not independent proof that all those features are GT04
requirements. Likewise, no code/audit flag automatically grants acceptance.

### Smallest next implementation

Add one bounded Blender-owned public write slice over the existing native owner
and `DurableBlenderSession`: a registered writer grant plus `mesh.create_box`
first, with typed transform/declared UndoRedo as its immediate follow-on. Keep
the common core and native command schema unchanged. Persist a public binding
record before dispatch and a byte-exact common terminal Response afterward.
Allocate a private command key in the native identifier grammar; public IDs use
a broader grammar and must not be forwarded or truncated directly. The binding
must keep both the common digest and complete private translation/context.

First evidence should be one separate authenticated client creating exactly one
object, duplicate/conflicting retry, unauthorized/expired/stale writer rejection,
lost response and restart lookup returning the original terminal or retained
UNKNOWN without redispatch, plus concurrent Stop and verified owned cleanup.
Supply a bounded dry-run/diff and declared undo/recovery policy; use checkpoints
for destructive changes. This slice is an implementation step, not GT04 closeout.

Then connect the same public binding to the existing fixed save/checkpoint/export
owner and protected selected bundle, and run required Object/Edit/context,
UndoRedo and mesh/transform/material reopen regressions on one final closure.
General crashed-GUI writer rearm and cross-app activation stay closed for GT07.
GT04 still needs its full supported-operation evidence and two independent
same-source critics; this map neither ticks the plan nor changes its DoD.
