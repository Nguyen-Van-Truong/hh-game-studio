# GT-01 frozen package verifier (r14)

`verify_freeze.py` is a read-only, fail-closed gate for the final GT-01
package. It recomputes the source closure hash from required files, hashes the
files on disk, binds every official runtime record and log to that closure,
and rejects candidate/diagnostic evidence, stale logs, warnings/errors,
timeouts, unverified process trees, unsafe paths, duplicate JSON keys, and
failed post-run checks. It never launches an engine or deletes files.

Example:

```text
python verify_freeze.py --source-manifest <manifest.json> --evidence <evidence.json> --repo-root <repo> --output result.json
```

The r13 runtime is intentionally expected to remain `GAP` until its status is
upgraded by a real official remint and two independent critics. Synthetic
mutation coverage is in `test_verify_freeze.py`.
