# Owned managed-fixture validation

`validation_owner.py` is a trusted local issuer for the finite script/scene
profile. `ValidationOwner.validate(command_id, bundle)` alone launches the
pinned Linux executor in `profile-validate` mode and can register a receipt.
There is no API accepting a caller result dictionary or callback as validation
authority. `evaluate_run` is a pure rejection helper and cannot mint receipts.

The factory first checks all eleven content files against the closed grammar
and nine installed release sources. The owner materializes exact eligible
bytes in a fresh directory under its trusted host-owned evidence parent. One
fixed helper performs parse, import and fresh script/scene readback. Receipt
registration requires phase order, sole observation marker, typed native exit
and PID zero, complete checked Windows Job cleanup/EOF, released admission,
exact input/harness/binary hashes and clean logs. Observed values are compared
to the eligible bytes, including typed exported defaults and scene overrides.

The module snapshots runtime source before consulting addon caches and checks
the exact loaded factory, stager, codec, profiles and CLI module against that
snapshot. Creating a later issuer cannot adopt changed disk bytes while old
dependency code remains loaded; release drift rejects even before a new run.

Receipts bind command, complete bundle manifest, installed runtime sources,
Linux engine, observation and full retained evidence inventory. They work only
by object identity in their original live issuer. `observation(receipt,bundle)`
rechecks source/evidence and returns a detached historical observation. A copy,
foreign issuer, changed bundle, changed evidence or closed/held owner rejects.
Duplicate attempts never implicitly rerun Godot. Any interrupted or failed
attempt after evidence creation holds the issuer; KeyboardInterrupt/SystemExit
propagate after the executor's own cleanup path. Closing the issuer does not
remove retained diagnostic data or clear a global executor cleanup hold.

There are at most four attempts per issuer, a 5–20 second native deadline,
the executor's global admission maximum of one, and bounded fixed input and
log writers. Evidence inventory is limited to 256 files/16 MiB per attempt
(64 MiB across four); exceeding the post-run check cannot yield a receipt.
This inventory bound is not an independent filesystem quota. Native container
tmpfs/resource limits and per-stream host capture caps still come from the
executor. Only the trusted host supplies `evidence_parent`; no remote path is
accepted. The installed Python host/release is trusted, and release edits
require a fresh process/issuer rather than hot reload.

This is internal validation, **not publication**. A receipt does not prove
selection, editor adoption, file/directory barriers, current lease/fence or a
semantic scene revision supplied in bundle metadata. In particular it cannot
turn that caller observation into an actual EditorPlugin semantic revision.
The publisher must bind those effects and original command authority before
any public response. `public_ack` and `selected_state_verified` remain false.
The engine field identifies the Linux validation pin; any Windows editor
adoption must separately bind its platform pin and actual readback.

The component probe retains failed native constructor cleanup owners/APIs and
does not remove its owned temporary root until checked closure succeeds.

Unit tests replay saved native observations for rejection and explicitly mock
the executor for issuer bookkeeping. Those tests are not fresh engine proof.
Actual validation-owner runs are recorded separately with owned process exit,
source freeze and complete artifact hashes.
