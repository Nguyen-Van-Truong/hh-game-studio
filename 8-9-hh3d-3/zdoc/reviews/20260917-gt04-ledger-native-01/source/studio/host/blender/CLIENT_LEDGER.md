# Unadvertised Blender client ledger

AUTHORITY=0. This component is not attached to a public route or capability.
It records Request/private-operation associations and common Response bytes.
It does not execute Blender, authorize a writer fence, prove native readback,
publish artifacts, recover a GUI, or issue a public durable ACK. Existing
read-only facade and native owners are unchanged by this component.

## Backend and binding

`BlenderClientLedger.from_owner(exact_owner)` accepts only the existing exact
live `BlenderClientOwner`. It checks that owner before and after opening the
fixed `client-ledger/client-commands.jsonl` beneath its private GUI directory.
The path is not a Request field. A caller cannot supply a journal, native PID,
project path, executable, saved storage descriptor or replacement backend.

The immutable configuration binds project, native generation, runtime source
digest, catalog digest and the registered owner's identity-pin digest. Every
intent repeats that configuration and records authenticated session ID, complete
public command ID, Request digest, original Request bytes/hash, and private
operation bytes/hash. Public IDs are hashed in full into a lowercase 47-character
private alias. History rejects mismatches/collisions; IDs are not truncated or
normalized into the private grammar.

The unchanged GT02 `Journal` is the storage primitive. The adapter follows the
existing `BlenderWriterJournal` pattern: compound decisions under
`Journal._mutating`, using the existing append/finish implementations within
that same native lock. Reload barriers, checksums, private-path checks and
terminal reservations remain in core. A fresh complete readback follows each
append before this layer returns a new admission marker or terminal response.

This is the local cooperating-owner journal contract, not protected publication
custody. Checksums do not prove resistance to a privileged writer replacing a
whole valid history. No rollback witness, cross-host storage, power-loss proof,
arbitrary-path safe-write authority or new durability primitive is invented.
See [the existing backend contract](../core/JOURNAL.md).

## Typed private operations

The target is exactly `{"stable_id":"blender.owned-scene"}`. Inspect uses an
empty public payload and the existing private inspect command. All other
Requests use `{"expected_context": ..., "arguments": ...}` so context is bound
by the common Request digest. Create, transform, material and owned undo/redo
arguments must match their validated native UI payloads. Public `scene.save`
and `checkpoint.save` accept empty arguments and select native `fixture` and
`checkpoint` slots respectively. `export.publish` accepts empty arguments and
binds a `HH-BLENDER-PUBLICATION-1` request, not a fabricated UI export receipt.
Its outer private publication ID is the ledger alias; the publisher remains
responsible for its own internal native commands. Paths are not accepted.

These are unadvertised integration shapes, not additions to the current public
catalog. The future facade still must perform capability/schema validation,
source/PID/Job binding, lease/fence and actual-effect deadline checks, native
postconditions, capacity reservation, and Stop/revocation accounting.

## Lifecycle and exact replies

`begin(grant, request, private_operation)` validates the registered operation
grant and secret-safe identifiers/data. It persists INTENT before returning an
opaque in-process admission marker. That marker proves only ledger admission;
it is not a writer lease or permission to dispatch without the other gates.
Copies, completed markers and markers from another instance cannot finish work.

`finish(marker, response)` stores a terminal COMMITTED, REJECTED, CANCELED or
UNKNOWN common Response. The response must explicitly carry
`public_ack=false` and `ledger_receipt_only=true`. Recorded COMMITTED can mean
an observed unsaved editor effect; it does not make live state or saved files
durable. Native/publication proof is a separate integration requirement.

Exact retries return the original bytes without new dispatch markers. Changed
operation/payload/context, expected revision or native translation conflicts.
Changed lease/fence/deadline may retrieve history but never change the original
Request or renew admission. Lookup is scoped to the registered session; token
rotation can retain that session while a different session cannot read it.
History remains readable after owner Stop or the retry horizon. An unfinished
intent returns a deterministic UNKNOWN with `dispatch_permitted=false`; neither
reopen nor expiry permits replaying it. An expired pending command cannot be
finished through a new admission.

Terminal persistence failure holds new admission and retains the exact marker
and attempted response for a bounded storage retry. A conflicting replacement
response is rejected. If a visible terminal survived a failed write, only the
backend's successful reload barrier and exact readback can return it later.
Guard-release failures after admission or terminal readback are also uncertain:
the facade holds new admission, reports a typed error with `outcome_unknown`,
and preserves any recorded intent and exact terminal retry. No permit escapes
an admission whose guard failed to close successfully.
No exception details or caller-declared success flags become acceptance proof.

Both input persistence and returned receipt bytes must survive the current
session redactor unchanged. Expanded secret history can deny later delivery;
it never rewrites or rehashes stored outcomes. The future transport must enforce
the same exact-byte rule at its final output boundary.

## Bounds and verification

The ledger keeps 32 command identities, one pending intent, and 65 records
including configuration. Request/native/Response byte caps are 8192/4096/32768.
Core reserves one full envelope and terminal record for each admitted pending
command. Limits use the unchanged default core profile and a 17 MiB journal.
Native queue/IPC/export budgets remain separate and must be reserved by the
integrating owner. No eviction, compaction or archive rewrite API is exposed.
An externally compacted/tombstoned or incomplete chain fails closed instead of
being interpreted as a new empty ledger.

`test_client_ledger.py` uses an explicitly inert in-memory harness: actual pure
core record validation/encoding and this layer's compound methods/reducer, with
no filesystem, native lock, Registry, engine, or storage integration calls.
Its concurrency/failure tests are model evidence. Actual native journal
reservation/barrier/lock behavior, owner binding and external-client integration
still require coordinator-run evidence on the complete frozen source. This
component cannot unlock GT04 or public writes by itself.
