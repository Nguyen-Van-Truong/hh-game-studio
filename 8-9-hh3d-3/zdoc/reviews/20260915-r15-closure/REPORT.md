# GT-01 closure remint report (r15)

Status: **READY_FOR_RUNTIME_REMINT**

The read-only closure generator found **20 required files**: pinned bootstrap runtime, sample game/Blender fixture sources, all bootstrap tests present at freeze time, and bootstrap/fixture documentation. The closure hash is:

`b4c2c972a6f83c058bc891e8bcae6d95fb8553fd108921e9324c02cb7197ce60`

The verifier recomputed every SHA-256 from the product tree, checked regular-file identity, rejected symlink/reparse/hard-link anomalies, rejected duplicate JSON keys, and found no host-path or secret markers. Caches, `.godot`, `.local`, evidence directories, temporary files and runtime output are excluded by policy and are not copied into the closure.

Commands run:

- `python closure_manifest.py generate` → `CANDIDATE`, 20 files, 0 gaps
- `python closure_manifest.py verify --manifest source-closure-manifest.json` → `READY`
- `python -m unittest test_closure_manifest.py -q` → 3 tests passed

This package does not run Godot, Blender, or the installer. Remaining GT-01 gates are a final source freeze after all source edits, one serial official Godot runtime remint bound to this exact closure hash (including TX12/TX14), archive/installer recovery evidence, and two independent read-only critics on the same frozen hash. The coordinator must perform acceptance and may not tick the plan from this report alone.
