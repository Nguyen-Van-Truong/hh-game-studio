# S49 diagnostic consistency audit

AUTHORITY=0. `acceptance=false`, `formal_acceptance=false`, and `public_ack=false`.
This package is tested implementation work, not GT03 acceptance or authenticated
publication. The known `cli_job.py` BaseException cleanup gap remains open for
the next bounded implementation slice. Passing these captured scenarios does
not establish correctness for that untested interruption path.

`verify_evidence.py` checks one identical, complete 107-file runtime source
closure across the current tree and the editor, Linux, and profile frozen copies.
It verifies actual Windows host reports, 321 Python tests, 103/10/31 editor
checks, 11 hostile fixtures, five eligible profile cases, and the separate
same-closure host-death experiment. Expected counts were fixed only after the
coordinator reported the completed captures.

The profile audit decodes each canonical candidate manifest with all 11 actual
files, qualifies its trusted release bytes, compares it to the frozen case,
and calls the source-bound native observation comparator. Raw phase order,
UIDs, file hashes, complete scene/instance properties, checked CLI Job close,
EOF, container removal, PID1 supervision, readonly project/tool/harness mounts,
resource policy, and exact snapshot bytes are checked. The host-death check
binds raw running/exited observations, observer streams, native timeout,
terminated host Job, concurrent admission denial, and exact orphan recovery.
Host-captured termination facts are consistency evidence, not external identity
authentication or public receipts.

The artifact manifest is coordinator-owned. Its inventory must exactly cover
every named review-directory root; standalone review files remain individual
entries. All four principal packages are mandatory. Only this audit directory's
`artifact-manifest.json`, `verification.json`, `git-byte-verification-index.json`,
and `git-byte-verification-HEAD.json` are excluded to avoid recursive inputs.
Historical failed/provisional packages may be inventoried for preservation;
their presence does not turn their results into passing evidence.

Run from the repository root, using a fresh Python process with a bounded host
timeout. No engine or Docker operation is performed:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s49-audit/test_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s49-audit/verify_evidence.py
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s49-audit/verify_evidence.py index
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s49-audit/verify_evidence.py HEAD
```

The last two modes additionally compare exact disk bytes to Git blobs in one
bounded `git cat-file --batch` call. They do not stage or commit anything.
Verification writes its summary only after all checks succeed.

Focused audit regression run: actual exit 0, 21 tests, 0.480 seconds, using an
explicit 40-second subprocess timeout. It includes a raw captured profile
baseline and negative cases for duplicate/nonfinite JSON, type/path aliases,
wrong mode, stale input hashes, missing admission release, forged ACK,
changed supervisor/create policy, writable or substituted mounts, incomplete
Job close, retained handles, malformed EOF/byte counts, missing native exit,
changed harness hash, and omitted/extra inventory files. These are pure tests;
the large tool hash is substituted only inside the regression suite. The full
verifier hashes the actual pinned binary and complete inventories.

Development checks reached the final inventory stage after recomputing all
four principal raw packages successfully. An initial audit-only reconstruction
mistake omitted Windows `write_text` CRLF translation; it was corrected without
changing engine source or evidence. Final whole-package/Git results must come
from the coordinator's fresh manifest and verifier outputs, not this README.
