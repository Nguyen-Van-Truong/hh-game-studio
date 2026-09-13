# GT-01 runtime readiness audit (r13)

`2026-09-13`, read-only audit; no Godot or Blender process was started.

## Finding

The pinned Godot console and GUI files are discoverable under
`studio/.local/tooling/godot-4.7.2-stable/`. Their SHA-256 values match
`studio/toolchain.lock.json` (`c8f0…6643` and `ab18…2424`). The 1.28 GB export
template archive is present, but the lock intentionally records
`ARCHIVE_VERIFIED_NOT_INSTALLED`; it is not required for the GT-01 headless
fixture run. No Godot/Blender process was active during this audit.

The official-runtime item remains a **GAP/PENDING evidence condition**, not a
missing-file condition. The lock is still `status=CANDIDATE`, and the repository
does not yet contain one fresh host-captured run bound to a complete frozen
source closure, independently captured process exits/tree proof, and two
critic records on the same source hash. Existing candidate/partial logs cannot
be promoted by this audit.

## Admission checks covered

`test_runtime_readiness.py` exercises the production runner without launching
an engine: missing executable, caller hash/version mismatch before probe,
non-zero exit or unverified process-tree evidence becoming `DIAGNOSTIC`, and
host-path redaction with portable argv. This complements the bootstrap suite;
it does not prove official runtime execution.

## Next bounded command

After source freeze and a single-process reservation, run the exact command in
`studio/build/bootstrap/README.md` with a new `run_id`, `command_id`, and a new
output directory outside `studio/`. Capture the host exit and leftover proof,
then generate the complete closure manifest before critic review. Do not run a
second engine against the same fixture path.

`python 8-9-hh3d-3/zdoc/reviews/20260913-r13-runtime/test_runtime_readiness.py`
