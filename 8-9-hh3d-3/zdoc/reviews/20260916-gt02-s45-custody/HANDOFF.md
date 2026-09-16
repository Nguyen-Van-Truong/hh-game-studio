# S45 standalone registry custody handoff

Implementation completed without editing the coordinator's supervisor, protocol,
plan, safe-open capability flags or other workers' source. No commit or gate tick.

Owned source:

- `studio/host/core/custody_registry.py`: `54a45327faf5630f750108781e427c0b01f04ae6482df7d2572dfba1b6ea3db2`
- `studio/host/core/CUSTODY_REGISTRY.md`: `8217b8d27e55a374de49ee48f3179fa7c427c833d06fcd0572be6c296f80ca37`
- `studio/tests/protocol/test_custody_registry.py`: `7b014244f5808a8aed4a51ccc592d6c14d72fe624f82da45135ae984b107f72e`

API: `RegistryCustody.provision_base()`, `create(local_id)`, `reopen(local_id)`,
`read()`, `store(data, expected)`, `close()`, and read-only `local_id`.
The coordinator's supervisor owns the opaque canonical/checksummed record and
must hold its exclusive file writer guard during updates. The registry module
does not claim cross-process CAS. Public capabilities remain disabled.

Focused `run-02` passed 21/21, no skips, actual exit 0 and verified owned tree.
Three actual child cuts exited 81 at empty provisioning, before the state
barrier and after the barrier. Fresh empty reopen refuses incomplete
provisioning; visible data is exposed only after a fresh barrier. Additional
coverage includes native configured/unfinished registry links, actual DACL
tampering, conflict preservation, state shape/size, and retained actual key,
token and security-allocation ownership after injected cleanup failures.

Native boundary evidence:
`../20260916-gt02-s45-registry-native/run-02/` matches final supplied S45-02
closure `26a225b45f8283796448512987595fd962cad204e6c57164c3929ee7a067c243`
(97 files). A zero-capability low-integrity AppContainer made 45 attempts:
opens for query, set, DELETE, WRITE_DAC, WRITE_OWNER, create-subkey and
READ_CONTROL, plus direct key deletion and subkey creation. All returned
access denied; none were allowed and no unexpected errors occurred. An
explicitly package-granted low-integrity control leaf under the same actual
user-hive prefix allowed native read/write, verified by the host.

The trusted host held a native exclusive file guard and completed 12 expected
registry updates while the adversary ran; actual State/Format checks passed.
Child exit was 89, its Job active count was 0 with an empty PID list. Compiler
and linker exited 0 with no surviving helpers. Outer probe exited 0 with a
verified owned tree and final empty PID list. Both recorded UUID registry
leaves, owned AppContainer profile, temporary files and snapshot were removed.
Source and immutable snapshot hashes were unchanged. Native stderr was empty.

`s45-registry-native/run-01` is preserved as successful evidence for the older
S45-01 closure `497b26030b39f4fcf515bce414ff7708473323f5a4566b10791fcc44660ee58c`.
The coordinator changed a transport test after that run, so run-02 is the
matching remint. No signatures or results were transferred across closures.

The fixed product registry base was absent during the initial audit. The
coordinator authorized explicit one-time protected parent provisioning.
This worker's first captured focused setup found compatible parents already
present (`created_components=[]`); it did not alter existing parent ACLs.
Native/individual tests used only new disposable UUID leaves, deleted by
verified no-follow key handles. Shared product parent keys remain configuration.

These are implementation and boundary results, not an independent acceptance
verdict. Whole-candidate regression, supervisor integration and two independent
critics remain coordinator responsibilities. Physical power-loss certification
and rollback by a trusted owner/admin are not claimed.
