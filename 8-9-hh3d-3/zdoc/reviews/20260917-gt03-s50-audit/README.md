# S50 diagnostic audit

AUTHORITY=0; acceptance, formal acceptance, public ACK, selected-state proof and
semantic scene-revision proof remain false. This is a consistency audit of
captured implementation diagnostics, not GT03 acceptance.

The adapter pins the S49 verifier to SHA-256
`ad040b4512fbdfd865131a7d281ca958fad853cee36b1c21e3e0b2870338271f`.
It changes only the two exact `S49_IDLE_BODY_AFTER_HOST_DEATH` literals to the
S50 marker in memory, then explicitly binds the S50 package paths and counts.
The original file stays unchanged. This reuses verification logic, not earlier
test results or signatures.

Required S50 packages are editor-01, linux-01, profile-01, host-death-01 and
components-01, with the same frozen closure
`e6fcee30d7000aef5a5781e7cebe04c08e2be9a961c033fae3f0926d1e44bc3d`.
The actual completed editor capture supplied the fixed 421-test count, with
zero failures/errors/skips and 103/10/31 engine checks. The reused audit checks
the complete current/frozen source, raw owned-process evidence, eleven hostile
fixtures, five eligible profile cases, resource policy, readonly harness,
checked native CLI Job cleanup/removal and independent host-death experiment.

The component extension decodes both complete eleven-file candidates from
their actual manifests/input bytes. It checks the exact default/script-change
pair; 24 unique generated native names/FileIDs on one root; every descriptor's
hash, length, volume and identity; raw executor phases and full native engine
observation; validation source-release binding; and all captured receipt fields,
including the canonical complete evidence-inventory hash. It checks actual
outer host exit/tree and exact completion markers. Canonical observation
comparison follows the issuer's actual JCS serialization step.

The protected temporary root was closed and deleted by the frozen runner.
Consequently, native barrier/readback/readonly-reopen facts are historical
assertions bound to that actual host execution and source. This audit cannot
independently reopen a currently existing root or register a receipt from JSON.
It never claims either. It runs no engine, container or native file operation.

The coordinator owns `artifact-manifest.json`, which must cover the exact
inventories of all named review-directory roots, including mandatory components.
Standalone review files remain individual entries. Only the current audit's
manifest and generated verification/Git-verification JSON outputs are excluded.
The pinned S49 helper is checked separately by its exact embedded hash; listing
any file inside that older audit directory additionally requires its full
directory inventory under the reused inventory rule.

Run in a fresh Python process with a bounded outer timeout:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s50-audit/test_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s50-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s50-audit/verify_evidence.py index
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s50-audit/verify_evidence.py HEAD
```

Git modes retain the bounded single `git cat-file --batch` exact-byte proof;
they never stage or commit. Failed verification writes no successful summary.

Nine focused pure adapter/component tests passed (actual exit 0, 2.267 seconds,
40-second subprocess bound). They include the actual captured component
baseline and tampered dependency, descriptor, native identity, receipt-evidence
hash and scope/type checks. An initial audit-only comparison error treated raw
integral floats differently from the issuer's canonical stored observation;
that check was corrected to reproduce the actual serialization. No component
or engine evidence was changed. Final whole-package/Git proof comes from the
coordinator's completed captures and fresh artifact manifest.
