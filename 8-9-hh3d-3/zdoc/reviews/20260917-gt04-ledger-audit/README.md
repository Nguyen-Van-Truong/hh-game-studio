# S55 Blender ledger component evidence

Candidate component, not GT04 acceptance or public write capability.
`../20260917-gt04-ledger-native-01` froze 117 files with source closure
`a18e6de9563e770fe7258242c369abdef04f2af692995360ff3f5402b488d9b7`.
The focused inventory passed 42 tests: 30 ledger and 12 probe gates.
Actual Blender GUI plus real Journal completed 25 checks. Target/wrapper
exits were zero, native Blender PID15640 exited zero, owned Job was empty.

The probe persists the common Request/private-command binding before its one
new native inspect. Separate Journal instances reread the original intent,
exact terminal and unresolved second intent. Retrying or looking up either
identity never resubmits the native command. A separate authenticated session
cannot read that terminal. Stop reached the observed native state in this run;
16ms is this workload's observation, not a general latency guarantee.

`verify_evidence.py` checks complete snapshot hashes, raw target/GUI exits,
native launch source, owner identity, three captured journal chains and exact
common/native response bindings. It performs file reads and pure reductions;
it does not open a Journal, Registry/native custody handle or engine.
`test_evidence.py` supplies nine in-memory corruption cases. The portable
manifest includes only explicitly consumed source and evidence. The probe's
broader local `evidence-inventory.json` is not a portable storage manifest and
does not authorize committing private directories, `.writer` or cache files.

The independent component review in `../20260917-gt04-ledger-review.md` found
and closed the guard-release uncertainty defect. Its final runtime/test hashes
match this source. After that review, four explanatory sentences were added to
`CLIENT_LEDGER.md`; the document hash in that review is historical. This native
closure binds the updated document. There is no GT04 acceptance signature.

Reopened Journal instances here belong to the same live registered owner.
This is not recovery of a crashed GUI or an external HTTP write integration.
Public writer grants, typed mutations, durable publication binding and final
same-source GT04 regression/critics remain to be implemented and verified.
All receipt claims retain `public_ack=false` and `ledger_receipt_only=true`.

From repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-ledger-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt04-ledger-audit/test_evidence.py
```
