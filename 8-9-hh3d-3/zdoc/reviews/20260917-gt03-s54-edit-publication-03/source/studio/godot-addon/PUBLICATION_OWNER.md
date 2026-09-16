# Managed editor and publication candidate

`GodotPublicationOwner.create` provisions one fresh owned fixture. Actual Linux
validation binds complete project semantics before the Windows editor and
native selected bundle are opened. Local provisioning chooses owned paths;
remote requests never choose native paths or executables.

Work routes: `/v1/discovery`, `/v1/lease`, `/v1/commands`. Separate control
routes: `/v1/lookup`, `/v1/stop`. Bearer and `X-HH-Catalog` bind exact
issuer/session/project/operation authority. Read leases remain independent of
the writer lease and available after Stop/drain. Secrets stay out of receipts.

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
The control listener never waits on disk/engine I/O. Stop's owned persistence
drain waits for serialized work, appends STOP and verifies it. Responses report
stop_persistence PENDING, DURABLE or UNKNOWN. Close retains a still-draining
owner. Uncertain native effects or durability failures never become ACKs.

Bounds: save/script writer horizon 90 seconds; other commands/read leases
30 seconds; native effect intent at most 10 seconds; Linux retains its separate
20-second quota. Each editor has 16 effect slots. An edit uses capture+edit;
admission reserves two further slots for save. Validator capacity is four runs
including bootstrap. Command/phase/journal/blob limits are checked before
admission. These are explicit fixture limits.

`GodotRecoveryHost.open` uses a separate catalog/bearer and a lease seeded above
durable fencing history. Actual fresh editor readback and a same-custody
terminal are required. A fresh HTTP host replays that terminal before another
attempt. This route never enables writable restart or erases original UNKNOWN.

Native harnesses: `run_edit_publication_probe.py`,
`run_script_publication_probe.py`, `run_publication_stop_probe.py`, and
`run_recovery_publication_probe.py`. Each freezes source and captures actual
target/wrapper exit and owned cleanup. Remaining gate requirements live in the
tools plan.
