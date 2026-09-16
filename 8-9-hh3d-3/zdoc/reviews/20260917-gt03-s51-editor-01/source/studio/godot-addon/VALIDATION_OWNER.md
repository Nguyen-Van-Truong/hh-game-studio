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

There are at most four attempts per issuer, a 5â€“20 second native deadline,
the executor's global admission maximum of one, and bounded fixed input and
log writers. Evidence inventory is limited to 256 files/16 MiB per attempt
(64 MiB across four); exceeding the post-run check cannot yield a receipt.
This inventory bound is not an independent filesystem quota. Native container
tmpfs/resource limits and per-stream host capture caps still come from the
executor. Only the trusted host supplies `evidence_parent`; no remote path is
accepted. The installed Python host/release is trusted, and release edits
require a fresh process/issuer rather than hot reload.

This is internal validation, **not publication**. An ordinary validation receipt
does not prove selection, editor adoption, file/directory barriers, current
lease/fence or a semantic scene revision supplied in bundle metadata. It cannot
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

## Binding an observed candidate revision

`bind_semantics(original_receipt, original_bundle)` first rechecks the issuer's
registered observation, complete raw evidence and loaded-source identity. Only
a schema2 report containing the full shared serializer snapshot is eligible;
historical schema1 property comparisons cannot satisfy this operation. The host
recomputes canonical state bytes and revision, checks input serializer/JCS pins,
then creates a **new** final bundle using the same eleven engine-input bytes and
the observed candidate revision. Its manifest is new metadata, never an engine
input or an overwrite of an already staged immutable manifest.

The return value is `(final_bundle, SemanticValidationReceipt)`. The original
bundle/receipt retain their original identities and metadata. The registered
final receipt binds complete input metadata, final manifest/project revision,
semantic revision, original run/evidence/source hashes and validation completion
time. Repeated binding returns the same registered result without running Godot
again. A caller-copy, changed file or changed evidence cannot acquire authority.

`semantic_observation(final_receipt, final_bundle)` rechecks original provenance
and returns explicit `context_kind=isolated_candidate`. Its engine field is
`validator_engine_sha256`; it never invents a live editor session or equates a
Linux process with the Windows editor. Actual selected-state adoption still
needs a fresh editor observation under the editor's context and build pin.
Both selected-state and live-editor-adoption flags remain false, as does ACK.

The validation start/completion timestamps bound the host-owned run; neither
is an engine-reported snapshot instant. They cannot turn a pre-selection run
into a post-selection readback. Receipt fields are compared with an independent
issued-value snapshot before use, including the original validator build pin.
