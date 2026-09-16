# S51 internal protected selector test record

AUTHORITY=0. Implementation/storage verification only, 2026-09-17.
No Godot, Docker, public ACK, live authorization proof, accepted-core changes,
commit, plan tick or GT03 acceptance is claimed.

Frozen files (relative to `studio/`, SHA256):
- `godot-addon/protected_bundle.py`: `263e2253ee83f0ee9086159dc3aa9ab83843614751299f12bf5fec94090e2032`.
- `godot-addon/PROTECTED_BUNDLE.md`: `e1d7f1f805695d6f1682dfda4a1afc6c29353bd75660f719248cc3976354fea5`.
- `tests/godot/test_protected_selector.py`: `a52d3795d94373c3e34f54f790c17833682c85a3f9a5c4611fdf3e7a0f76cba2`.
- Unchanged `tests/godot/test_protected_bundle.py`: `996a1b77178161a1044c10786d3e381bad5685d18f4229a8e3db0af44e36388a`.

Actual captured commands, invoked from the repository root:

```text
python -B 8-9-hh3d-3/studio/tests/godot/test_protected_selector.py
Ran 17 tests in 30.750s — OK, process exit 0, no skips.
python -B 8-9-hh3d-3/studio/tests/godot/test_protected_bundle.py
Ran 22 tests in 20.632s — OK, process exit 0, no skips.
```

Both suites used fresh actual Windows protected roots; cleanup checked the
exact originally captured temporary parent before removing owned test data.
The native selector suite initialized bundle A, atomically selected distinct B,
verified A's immutable receipt after the transition, and reopened both bundles
and current selector through a permanently readonly owner. CAS used A's exact
FileVersion and the actual native selector file/directory barrier was checked.

The suite covered registered intent/snapshot/receipt identity and value checks,
write-free preparation, strict six-key canonical selector schema, generations,
descriptor/root hashes, historical duplicate replies without a second CAS,
stale/foreign/copied objects, detached returned JSON, native response loss on
create and replace, faults after actual barrier and full-bundle readback,
external selector change before CAS, and close failure retaining cleanup owner.
Cancellation coverage included duplicate cancellation, canceled restage/reuse,
changed payload, copied intent, name tombstones, all 64 retained tombstones,
started-write rejection and unexpected planned files without deleting anything.

Initial test drafts exposed test-fixture mistakes: attempting to mutate the
codec's immutable mapping and asking the shared canonicalizer to encode an
unsafe integer. Only the new test fixture/assertion path changed afterward;
the final storage source hash above was unchanged across those test drafts.
The unsafe-integer case now directly checks the public preparation rejection.

The sole future journal owner must durably record intent before invoking stage
or select, derive semantic selection identity, and recheck live session/lease,
Stop and custody at publication. Storage intentionally supplies no callbacks,
authorization or engine validation. CONFIG metadata alone is not initial native
selection proof. Selector receipts remain `public_ack=false` and
`engine_effects_verified=false`; replay/reopen never rearm writes.
