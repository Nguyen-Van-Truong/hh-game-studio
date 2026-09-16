# GT04 protected publication03 component audit

AUTHORITY=0. Implementation evidence only; no GT04 acceptance or critic signature.
`public_ack=false`, `live_scene_recovered=false` throughout this bounded slice.

Frozen package: `../20260917-gt04-publication-03/`.
Source closure: `fc54433ac4a373e6e79aac33de1e6641e1a434cf2894a8ced622a445db36cd20`.
The package ran 135 Python tests and 16 native checks. Its source snapshot and
live source matched at capture completion. These results belong to this closure;
earlier cleanup/durable/material/FIFO packages keep their own closures unchanged.
The audit verifies 97 frozen source files and 152 portable artifacts. Its 14
tests include the real package and 13 tamper cases (raw exits, native marker,
Job leftover, response, custody witness, selector, checkpoint/GLB bytes,
native revision, truncated event suffix and a rehashed wrong terminal).

Run from the `8-9-hh3d-3` directory:

```
python -B zdoc/reviews/20260917-gt04-publication-audit/verify_evidence.py --check-live
python -B -m unittest discover -s zdoc/reviews/20260917-gt04-publication-audit -p test_evidence.py -v
```

The verifier reads only portable files and imports frozen pure validators; it
does not reopen native storage, Registry or Blender. `--check-live` is optional:
it checks current bytes and will correctly fail after any later source change.
`--write-derived` explicitly rebuilds verification and artifact hash inventories.
Reproduce a new native run with a fresh output directory:

```
python -B studio/tests/blender/run_publication_probe.py --output zdoc/reviews/NEW-UNIQUE-PUBLICATION-RUN
```

The owner publishes only the fixed owned checkpoint.blend/scene.glb/manifest.json
bundle plus active.json. Native output files keep their inherited Blender ACLs;
capture checks the exact private export directory, pins native file identities
and hashes while reading, then copies canonical bytes through unchanged GT02
ProtectedFileRoot creation/readback/file+directory barriers. PrivateBlobStore
mirrors are non-authoritative staging provenance. Registry WitnessCustody anchors
the binary PrivateEventLog chain before effect and after terminal publication.

Evidence covers foreign path/mode rejection before intent; owned UI mesh,
transform and original Principled material; capped separate background export;
full GLB geometry/TRS/material binding; selector and complete artifact versions;
injected reply loss after witnessed terminal; exact duplicate response with no
second export; conflicting duplicate; read-only storage reopen; actual GUI and
background exit/Job-zero; fresh native Blender reopen of the protected checkpoint.
The portable verifier binds raw captured process exits, source maps, six binary
events and their exact custody witness, canonical response and selector bytes,
staging mirror hashes, all protected files and fresh native readback. File IDs
and Registry records are captured native evidence, not revalidated by this
portable audit on another machine or after a Git checkout.

Failure history is preserved: publication01 stopped before protected artifact
writes on PRIVATE_ACL_CHANGED because native inherited file ACLs are not the
PrivateBlobStore grammar. Publication02 passed that capture repair but stopped
on PUBLICATION_NATIVE_SNAPSHOT: durable JCS converts integral floats to integers
while Blender's scene revision distinguishes them. Publication03 stores native
canonical snapshot JSON as text, validates its original digest, and binds its
semantic value to the normalized manifest. No core ACL relaxation or epsilon
change was made; two new unit tests cover normalization and tamper rejection.

Limits remaining: one bundle per owned GUI/storage generation; only the bounded
original mesh/material profile. No arbitrary .blend, live GUI state recovery,
artifact replacement, public transport/ACK, Godot consumer/import or full
cross-app activation. Incomplete prefixes return UNKNOWN without effect replay;
this run cuts the reply after a durable terminal, not an OS crash at every disk
phase. Publication-specific crash/selector/Stop/disk-failure recovery coverage
and final same-closure independent critics remain required. Prior component
checks do not become final GT04 acceptance by aggregation. Physical power loss
and unrestricted broker-account/admin tampering remain outside this proof.
