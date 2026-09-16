# Managed editor and publication candidate

`GodotPublicationOwner.create` provisions one fresh owned fixture. Actual Linux
validation binds complete project semantics before the Windows editor and
native selected bundle are opened. Local provisioning chooses owned paths;
remote requests never choose native paths or executables.

Work routes: `/v1/discovery`, `/v1/lease`, `/v1/commands`. The separate control
listener serves `/v1/lookup`. The canonical `stop_port` serves only `/v1/stop`;
control-port Stop remains available for compatibility. Bearer and `X-HH-Catalog` bind exact
issuer/session/project/operation authority. Read leases remain independent of
the writer lease and available after Stop/drain. Secrets stay out of receipts.

Writer admission also exposes `/v1/lease/enqueue`, `/v1/lease/poll` and
`/v1/lease/cancel`. Enqueue carries project_id, request_id, ttl_ms and wait_ms;
poll/cancel carry project_id and ticket_id. Eight live waiters and 64 lifetime
tickets bound memory. Only the FIFO head can receive a registered lease; the
legacy immediate route uses the same queue and cancels its own waiter when
busy. Ticket retry preserves the original parameters, deadline and terminal
outcome. A historical GRANTED ticket never revives an expired/stopped lease.
Discovery reports the remaining lifetime ticket budget. At exhaustion it
advertises writes only to a caller with an existing exact unexpired writer
lease, so that caller can still save; once that lease expires only reads remain.
Cancel during granting reports uncertain issuance; the hidden unused lease
expires before the next writer. Tickets/grants are volatile across restart;
durable command outcomes remain in the protected journal.

The catalog enables inspect, bounded script diff preview, typed node
create/update/remove, UndoRedo, scene save and declarative script replacement.
Mutations bind semantic revision, selected project revision, generation,
lease/fence and deadline. Each phase and native effect recheck their context.

Editor edits use one protected stream: EDIT_INTENT, actual capture, EDIT_READY
after private checkpoint blob/readback, native edit, then EDIT_COMMITTED after
registered observation. V5 preserves original V4 event bytes. Its response
explicitly states editor-session scope, unsaved files and non-durable live
state. Native UndoRedo history survives edits. Historical retry remains exact
after later edits; inspect reports current state. Changed digests conflict.

Scene save captures the dirty scene, validates eleven inputs in Linux,
stages/readbacks twelve protected objects, journals selector intent, performs
native CAS and records selected FileVersion. Same-editor reload/readback
precedes durable COMMITTED. Script replacement includes dirty scene and new
script in one bundle, retires the old editor and reads back a new generation.
Both create an explicit history boundary; old generation UndoRedo is rejected.

Stop/revocation deny unused permits immediately and account for started phases.
Stop admission never waits on disk/engine I/O. Historical lookup may perform
I/O, with one admitted lookup and explicit `GODOT_LOOKUP_BUSY` for excess
requests. Each listener has two bounded reader slots and validates its own
Host port. Incomplete work/control clients cannot consume the canonical Stop
listener's slots. Saturating Stop's own listener and arbitrary OS scheduling
are outside this isolation guarantee. Stop's owned persistence drain waits
for serialized work, appends STOP and verifies it. Responses report
stop_persistence PENDING, DURABLE or UNKNOWN. Close retains a still-draining
owner. Uncertain native effects or durability failures never become ACKs.

Bounds: save/script writer horizon 90 seconds; other commands/read leases
30 seconds; native effect intent at most 10 seconds; Linux retains its separate
20-second quota. Each editor has 16 effect slots. An edit uses capture+edit;
admission reserves two further slots for save. Validator capacity is four runs
including bootstrap, with one remaining attempt required before editing.
Discovery reports owner/effect/validator limits and remaining capacities;
exhausted mutation capabilities are disabled. A busy owner reports busy without
waiting for the current native operation. Admission always rechecks capacity.
Command/phase/journal/blob limits are checked before
admission. These are explicit fixture limits.

`GodotRecoveryHost.open` uses a separate catalog/bearer and a lease seeded above
durable fencing history. Actual fresh editor readback and a same-custody
terminal are required. A fresh HTTP host replays that terminal before another
attempt. This route never enables writable restart or erases original UNKNOWN.
Its own Stop drains to a typed durable recovery event; a freshly opened recovery
host exposes that stopped state and denies new work while retaining lookup.

Native harnesses: `run_edit_publication_probe.py`,
`run_script_publication_probe.py`, `run_publication_stop_probe.py`, and
`run_recovery_publication_probe.py`. Each freezes source and captures actual
target/wrapper exit and owned cleanup. Remaining gate requirements live in the
tools plan.
