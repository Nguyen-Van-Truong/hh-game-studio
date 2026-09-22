# GT06 S175 — official symbol availability boundary

`RUN_ID=gt06-s175-official-symbol-boundary-01`

`COMMAND_ID=cmd.gt06.s175.official-symbols.1`

`AUTHORITY=0`

`PROCESS_EXIT=NOT_APPLICABLE_READ_ONLY`

`LEFTOVER_PROCESS=0`

This is a read-only dependency attribution record. It does not run Godot,
CDB, Blender, the benchmark, or an installer, and it is excluded from the
GT06 dataset, F13, F14, leak claims, root-cause claims, and formal acceptance.

The official Godot build documentation states that official binaries do not
include debugging symbols and that a Windows MSVC build writes its symbols to
a separate PDB. The official 4.7.2 release page exposes Android native-symbol
archives, but no Windows PDB/debug-symbol asset in the release assets.

The pinned local Windows console binary remains
`Godot_v4.7.2-stable_win64_console.exe` with SHA-256
`c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643`.
The scoped local tooling and review folders contain no `.pdb`, `.dbg`, or
`.sym` file matching that binary. Building a custom Godot with symbols would
change the pinned runtime and is therefore not an admissible GT06 retry without
a separate owner decision.

## Decision

The external blocker is confirmed as a symbol/ownership capability boundary.
Keep `WAITING_EXTERNAL_INPUT`, preserve the stock source/profile/gates and do
not retry S169–S171 or launch formal 10x35. Resume only when a supported,
matching attribution capability is supplied; then use a fresh fixture ID before
considering formal GT06.

## Primary sources

- https://github.com/godotengine/godot-docs/blob/master/engine_details/development/compiling/introduction_to_the_buildsystem.rst
- https://github.com/godotengine/godot/releases/tag/4.7.2-stable
