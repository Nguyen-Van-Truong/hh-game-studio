# HH3D review evidence

Progress lives only in the two TXT plans one directory above.
Current review: [S19 / r7](20260911-r7/PLAN-AUDIT.md).

| Directory | Purpose |
| --- | --- |
| 20260908-r3 | Historical recovery and S3 review scripts |
| 20260909-r4 | Historical S6–S13 plan snapshots, diffs and critic evidence |
| 20260910-r5 | S14–S17 review and reusable Grok supervisor |
| 20260910-r6 | Current S18 progress, worker adjudication and partial GT01 runtime |

These are evidence folders, not worker processes. Worker workspace/output/logs
are separate attempts in local TEMP, referenced by ignored *.local.json files.
A worker completion notice does not accept its deliverable.

Keep reports, source hashes, frozen snapshots, diffs, validators and critic
verdicts referenced by plans or commits. They explain past decisions and support
reproduction. Do not blanket-ignore reviews or delete historical evidence merely
because its worker ended.

Python bytecode/cache and machine-specific *.local.json are ignored and may be
regenerated. No historical report or snapshot was removed in the r6 inventory.
At inventory, all review folders together occupied about 2.23 MB; the large
Godot/Blender downloads reside under ignored studio/.local/, not here.

Retention for future batches: commit a compact reviewed report, input/output
hashes, host exit, useful test logs and final diffs. Leave streaming logs,
tool downloads, duplicate workspaces and machine paths local. Before removal,
check references, active attempts, Git tracking and whether reproduction still
works. Owner permission to tidy does not mean successful/failed evidence should
be silently discarded.

