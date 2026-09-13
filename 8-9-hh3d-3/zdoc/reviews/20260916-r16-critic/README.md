# GT-01 whole-WP critic package (r16 template)

This directory is a **blank, read-only review template**. It does not claim
runtime acceptance and contains no critic signature. The coordinator may copy
`critic-a-template.md` and `critic-b-template.md` into isolated read-only
review sessions only after producing one final frozen source-closure manifest
and one official runtime evidence package.

## Dispatch invariants

1. Both critics receive the exact same `source_closure_sha256`, closure
   manifest hash, official run id, command id, and evidence package hash.
2. Each critic works independently from a read-only snapshot. A critic must
   not read the other critic's response, edit source/plan/evidence, launch a
   process, install software, or change credentials/configuration.
3. Any `CANDIDATE`, `PARTIAL`, `DIAGNOSTIC`, stale, missing, redacted-incompletely,
   or hash-mismatched artifact is a blocking finding. A green subprocess or
   exit code by itself is never acceptance evidence.
4. Each critic must return an explicit `TICK=yes` or `TICK=no`. Missing,
   ambiguous, or non-boolean output is `TICK=no` for coordination purposes.
5. Only two independent `TICK=yes` records over the same frozen closure and
   official evidence hashes can unlock coordinator adjudication. Critics do
   not tick the plan and do not provide human acceptance.

## Required input manifest

The coordinator must fill these fields before dispatch; placeholders are not
valid evidence:

```text
REVIEW_ID=20260916-r16
WP=GT-01
SOURCE_CLOSURE_SHA256=<64 lowercase hex>
CLOSURE_MANIFEST_SHA256=<64 lowercase hex>
OFFICIAL_EVIDENCE_SHA256=<64 lowercase hex>
RUN_ID=<unique reminted id>
COMMAND_ID=<unique id; never reused after source change>
PIN=Godot 4.7.2-stable
SNAPSHOT_ROOT=<sanitized relative snapshot identifier>
```

The coordinator must independently verify the manifest, official host exit,
trace/result line, version/checksum, stderr warning policy, and process-tree
cleanup before dispatch. A critic may report a gap; it must not repair one.

## GT-01 DoD coverage

The templates cover the complete GT-01 row: lock/reproducibility, fixture
isolation, archive/bootstrap verification, runner admission, official headed
and headless evidence, Windows/Linux process cleanup, Unicode/space paths,
candidate/cache isolation, and only the GT-01-scoped TX12/TX14 slices
(candidate/cache isolation plus quota/network/auth/Stop journal semantics).
ABI/template/build remains GT-08; full installer/migration/rollback/uninstall
remains GT-10; protocol/multi-agent recovery remains GT-02/GT-07.

