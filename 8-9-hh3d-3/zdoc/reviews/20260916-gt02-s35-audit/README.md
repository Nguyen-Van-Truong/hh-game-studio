# S35 coordinator checkpoint — CANDIDATE

Frozen closure: `264ed3e3f35ca76038ba20cc00f41f3345ba6e9352e111b3be5e7ed38fe6e111`.
This is solo verification, not two independent reviews or GT-02 acceptance.

`../20260916-gt02-s35-01/` contains 73 source hashes and 9 artifacts:
protocol 210 run / 206 passed / 4 explicit skips, bootstrap 56/56, actual
host exits and owned process-tree verification. Three skips require symlink
privilege; one is a Linux-only negative on Windows. Python/Node/Godot agree
on 2,396 canonical rows; Godot additionally rejects nine invalid inputs.

`verification.json` binds requirement IDs to observed passing test IDs and
verifies the stored native integration package on the same closure. The
native final run uses six actual AppContainer fixed-counter clients and a
separate wrong-client-PID negative. See its README for identity, readback,
exit and scope details. Decoder unit tests that substitute frame I/O are
not mislabeled as OS authentication proof; the native run supplies that proof.

`check_verifiers.py` passed nine portable/integrity cases: ordinary/optimized
native verification, integrated verification, explicit optimized-coordinator
refusal, changed log/manifest/source, missing artifact, and restoration. No
engine or full suite is rerun for metadata changes. Local raw/binary checks
passed; portable copies explicitly lack those ignored local files.

```powershell
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s35-audit/verify_evidence.py
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s35-audit/check_verifiers.py
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s35-audit/verify_git_bytes.py index
python 8-9-hh3d-3/zdoc/reviews/20260916-gt02-s35-audit/verify_git_bytes.py HEAD
```

The Git verifier reconstructs exact source/artifact/native dependency bytes
into an owned temporary directory and uses isolated Python to check them.
Its output records the actual commit/index checked; it does not rerun native
clients or claim a clean-clone runtime test. Metadata is outside the runtime
closure to avoid recursive source hashes.

Open work: integrate protected staging with a durable expected-generation
selector, intent/readback and explicit crash reconciliation; then freeze and
adversarially verify. General Windows safe-write/atomic replace are still
unsupported. Engine adapters remain dependent on GT-02; no later gate is
accepted. Native process-crash tests are not physical power-loss certification.
