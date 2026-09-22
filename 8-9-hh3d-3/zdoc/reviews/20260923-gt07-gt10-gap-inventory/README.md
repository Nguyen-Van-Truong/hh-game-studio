# GT07–GT10 static gap inventory — S175

`RUN_ID=gt07-10-readonly-gap-inventory-01`

`COMMAND_ID=cmd.gt07-10.readonly-gap-inventory.1`

`AUTHORITY=0`

`STATUS=PREPARATION_ONLY`

This is a read-only inventory of the current checkout. It does not open GT07,
GT08, GT09 or GT10, does not run an engine or installer, and is not an
acceptance result. The inventory prevents existing GT02–GT05 recovery and
publication tests from being mistaken for the later work-package gates.

## Confirmed missing target lanes

The following paths do not exist in the current checkout:

- `studio/host/leases/`
- `studio/host/jobs/`
- `studio/host/activation/`
- `studio/tests/ci/`
- `studio/tests/conformance/`
- `studio/package/`

`studio/build/` and `studio/toolchain.lock.json` do exist. Existing reusable
code is concentrated in `studio/godot-addon/`, `studio/host/blender/`,
`studio/host/core/`, `studio/host/replay/`, and the GT02–GT05 test families.
Those files are candidates for later implementation review, not proof of the
missing GT07–GT10 gates.

## Required order

Do not create these lanes or run their acceptance tests until GT06 is accepted
with attribution authority, full 10×35 runtime evidence and two same-hash
critics. When opened, each lane needs a fresh source/evidence freeze and its
own actual exit/cleanup/manifest proof.
