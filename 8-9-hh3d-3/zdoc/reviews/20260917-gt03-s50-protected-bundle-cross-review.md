# S50 protected bundle implementation cross-review

AUTHORITY=0. Read-only implementation review, not GT03 acceptance. No native
root, engine, Docker, or test process was launched for this review. No source
was modified. This review does not independently rerun the worker's native
tests or transfer their result into an acceptance claim.

Reviewed frozen files:

| File | SHA-256 |
| --- | --- |
| `studio/godot-addon/protected_bundle.py` | `660e40fc3dd0e7301216b55edb8aa7b8c194056bcc7dab2249c954d8c05933e7` |
| `studio/godot-addon/PROTECTED_BUNDLE.md` | `83ef3411c6db6ace6f8c834603bcde1bff7de879f92ebdd9ca2224c0ff4a3955` |
| `studio/tests/godot/test_protected_bundle.py` | `996a1b77178161a1044c10786d3e381bad5685d18f4229a8e3db0af44e36388a` |

No concrete defect was demonstrated within the documented standalone storage
contract. Constructor transfer, exact native type, shared marker, lock order,
registered intent/receipt identity checks and readonly rejection fit the
single-owner contract. Preparation creates all twelve names without writes,
allows one unfinished preparation and admits full byte/file quota plus selector
headroom before stage. Stage counts each write before calling native code,
retains returned FileVersions, checks full bytes/inventory, runs the native
manifest/directory barrier, then rereads the complete set before registering a
receipt. The relevant operation bodies catch BaseException and preserve held
cleanup ownership. Close retains the native-owner marker when cleanup fails.

Readonly descriptor reads authenticate declared identities against actual native
bytes and canonical bundle metadata without registering a command/receipt or
invoking rearm. Malformed caller descriptors reject before native reads;
uncertain reads hold the owner. The native tests cover actual quota boundaries,
same-intent concurrency, foreign/equal-copy objects, partial writes, barrier
and post-barrier faults, readonly reopen, and close failure. Cancellation has
no abort/reuse path: an unfinished preparation remains owned until lifecycle
shutdown. This is explicit in the current API and should remain explicit in
the future journal's Stop handling.

One concrete **P2 integration constraint**, not a defect in the current stated
scope: `protected_bundle.py:210`–`216` derives the complete expected inventory
from immutable constructor baseline plus registered staged files. An optional
baseline `active.json` is therefore pinned permanently; no method authorizes
changing its version. After stage, directly calling the transferred native
root's `atomic_replace('active.json', ...)`, or creating a previously absent
selector, makes the next readback/lookup reject with
`PROTECTED_BUNDLE_INVENTORY_CHANGED` and hold the store. This follows directly
from the exact inventory comparison; it was not run as a native probe here.
Two reserved slots and 32 KiB provide capacity only. A future journal/selector
must add a store-owned, explicitly verified selector transition under the same
lifecycle lock, or a reviewed equivalent ownership composition. It must not
silently retain a second native-root user or weaken complete inventory checks
to ignore arbitrary selector changes. The docs already say selection itself
is outside this slice, so this does not invalidate the storage test result.

Remaining assurance boundaries are unchanged: descriptor provenance requires
the future journal/custody layer; namespace durability is a historical native
byte/barrier observation, not engine acceptance; deliberate trusted-host
ownership violations are outside the Python wrapper's isolation contract.
