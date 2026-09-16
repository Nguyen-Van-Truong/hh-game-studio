# S51 semantic receipt binding review

AUTHORITY=0. Bounded read-only implementation review, 2026-09-17.
No engine, native run, source edit, formal acceptance or plan tick.
Reviewed SHA256, relative to `studio/godot-addon/`:
- `validation_owner.py`: `cdf4dd2ccba80f208cb6c3dfebc217c6f8801ee9a421a05534bf2fb5ad045f8b`.
- `profile_readback.py`: `0236697c298c80a965d880087d6bc63b4378161d3e7142fe1b0c81b8e2e19c7a`.
- `validation_bootstrap.gd`: `efde8370a6157ed2f66544ee13b82ee2556b59130f5306e9e0774ed0e3be79a5`.
- Journal fix recheck, `publication_journal_v2.py`: `79a597442abb7799bf75fbff651ad52bd7867c2f6d0847bf1bb5df99a80ea1d2`.

## Concrete finding

`observation()` validates the exact original ValidationReceipt object and its
observation hash, but not all its issued values against independent owner facts.
`bind_semantics()` then takes engine/source/evidence/run fields from that object
when constructing the final bundle and SemanticValidationReceipt. A holder of a
real receipt can mutate a frozen object's field through `object.__setattr__`;
changing `engine_sha256` can therefore relabel the new manifest's engine pin.
Likewise changed source/evidence/run fields can be propagated into new provenance.
Identity registration alone does not detect same-object value mutation.

This is trusted Python holder misuse, not a candidate-script execution path or
a forged JSON/copy acceptance claim. The existing store deliberately checks this
class of registered-object mutation. Apply the same bounded defense here: save
all issued receipt values independently in _Record, compare before observation
or binding, and derive new provenance from those owner facts. Test engine,
source, evidence and run-ID mutation separately; ordinary equal copies and
foreign owners must continue to reject. No executed exploit is claimed here.

## Binding and timing limits checked

The schema-2 helper obtains semantic state from the pinned shared
StoredSceneSnapshot serializer. Comparator checks shared JCS hash, exact
serializer/JCS source hashes, node IDs/owners/order, script identity, exports,
and finite bounded vectors in addition to the existing full fixture readback.
The receipt cannot be supplied as a raw dictionary: binding requires the
issuer's registered original receipt and byte-identical original bundle.
The final manifest changes caller observation metadata while all eleven actual
engine-input files remain byte-identical; no extra engine run is claimed.
Repeated binding preserves the original completion timestamp and registered
semantic receipt, rather than inventing a later observation time.

The semantic receipt correctly remains `isolated_candidate`, with public ACK,
selected-state and live-editor-adoption claims false. `observed_ms` is host
completion time after validation/evidence capture, not the instant at which
Godot captured the snapshot. It cannot by itself prove a future post-activation
READBACK; that owner must bind a new observation to the selected effect and
actual consumer start/order. This is an explicit integration limit, not a
current live-editor capability that the API advertises.

## Journal fixes rechecked

The reviewed correction now compares actual `inspect_selection()` bytes and
full FileVersion to the durable bootstrap SELECTED record. Missing selector or
same bytes under a recreated native identity no longer pass this code path.
`_store_operations` now translates child preparation, cancellation and STAGED
verification uncertainty into the outer journal cleanup owner/held state.
These close the two earlier findings by inspection; native regression results
belong to the coordinator's separate run.

One combined cancellation cut remains worth preserving: when pure preparation
raises KeyboardInterrupt and `cancel_unused_prepare` itself fails, the latter
exception replaces the original interruption. If this cut is supported, retain
the original BaseException with journal cleanup ownership while recording the
cleanup failure as its cause. No second owner or automatic retry is justified.
