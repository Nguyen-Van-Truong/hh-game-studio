# Scene-save publication journal, version 3

This internal journal stores a bounded `scene.save` history and owns the actual
native bundle store, active selector, event stream and registry custody. It does
not authenticate a client, run Godot, establish a validator result, or issue a
public committed acknowledgement. Engine and admission dictionaries accepted by
the typed methods are **attestations** that the separate publication owner must
derive from its registered receipts and current effect guards.

The version 3 reducer distinguishes the Linux `isolated_candidate` validation
from Windows `live_editor` adoption. The two engine hashes are independent.
`COMMITTED` in this internal fold means that a complete, structurally consistent
attestation chain has been persisted. Every returned record still states
`public_ack=false`, `engine_effects_verified=false` and `execution_permitted=false`.

## Durable order

Creation stages and reads back the initial eleven project inputs plus canonical
manifest. Bootstrap selection, its actual FileVersion, and CONFIG are durably
witnessed before the owner is returned. Ordinary scene saving then follows:

1. `capture_prepared`: persist original selected descriptor/FileVersion, editor
   precondition, admission and a unique scratch name before scratch capture.
2. `captured`: record the bound capture attestation. Ten non-scene inputs must
   exactly match the selected bundle; the captured scene semantics must match
   the caller's dirty-editor precondition.
3. `prepare`: reserve twelve native object names and persist PREPARED before any
   new native object is created. Invalid pure transitions cancel only an unused
   reservation; uncertain cleanup retains the outer lifecycle owner.
4. `stage_prepared`: reject expired admission before writing, then actually stage,
   flush and read back the complete bundle; derive the native descriptor from the
   store and append STAGED.
5. `validated`: bind the isolated-candidate attestation to the complete final
   manifest, semantic digest, eleven inputs, source release and validator pin.
6. `prepare_activation`: derive an exact registered selector intent and durably
   append ACTIVATING with the old expected FileVersion. `select_prepared` then
   performs the actual native CAS and persists SELECTED with its returned native
   identity, hash and size. The public owner must immediately precede that call
   with its live grant/lease/Stop effect gate.
7. `readback`: bind a fresh same-session editor adoption attestation to the
   selected inputs, native selector version, new root/generation and an explicit
   history boundary. `commit` durably records its exact event hash.

`lookup`, `selection_facts` and `read_selected_bundle` revalidate current native
owners, registry witness, full event history and current selector. The selected
descriptor is read from all twelve actual protected native objects, not merely
returned from cached metadata. Historical bootstrap objects remain immutable.

## Recovery and ownership

Scene-save admission is bounded by `MAX_SAVE_ADMISSION_MS=90000` and the current
lease expiry. This explicit operation-specific bound accommodates measured Linux
validation plus native custody checks; it does not extend individual editor effect
permits, bypass Stop, or change the accepted shared protocol/core limits.

Reopening is permanently read-only. It folds the entire version 3 selector chain;
it does not compare the current selector permanently with bootstrap. It cannot
resume capture, staging, CAS or adoption, and never privately rearms the accepted
GT-02 native store. A SELECTED-but-unadopted chain reports SELECTED, never COMMITTED.

A crash before CAS leaves the old selector and ACTIVATING history inspectable.
A CAS that occurred without a durable SELECTED witness produces a selector/history
mismatch and reopening fails closed. Missing/recreated same-byte selectors, changed
native FileIDs and changed selected content also fail closed. No automatic rollback
or retry is performed after an uncertain native effect.

Lifecycle ownership uses the unchanged version 2 checked native close path.
Cleanup stops at the first failed close and retains that owner and its ancestors;
explicit `close()` retries the same owners. KeyboardInterrupt/SystemExit survive
cleanup failure and carry the root cleanup owner. The pure reducer validates integer
types before comparisons and preserves bool/int distinctions in nested equality.

## Focused verification

From `studio`:

```text
python -B -m unittest discover -s tests/godot -p test_publication_journal_v3.py -v
```

The test uses real Windows protected roots, registry custody, file barriers, native
selector CAS, event persistence and read-only reopening. Its engine/auth facts are
explicitly synthetic. Successful tests therefore establish storage behavior only;
the separate installed EditorPlugin/publication integration must establish actual
capture, validation, adoption and authorization.
