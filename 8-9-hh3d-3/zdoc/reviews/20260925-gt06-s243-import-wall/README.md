# S243 import-stage timeout preservation (S244 packet)

Campaign `gt06-s243-formal-01` used fresh source closure `1f6b7da7f48085b417e5d6d7f3388c75c0a8beadad3659b14057a2a6e71df625` after the terminal-persistence repair. It did not reach batch 0: the Godot import stage terminated with `STAGE_WALL_LIMIT` after the bounded import wall. `completed_batches=0`, formal acceptance is false, and no partial benchmark data is eligible for merge.

The captured import stdout contains only the pinned Godot version; import stderr is empty. The child cleanup records the import target exit as unknown (`TARGET_EXIT_NOT_RECORDED`), with the observer closed, no retained probe handles, and no inferred natural exit. The host owner reports `owned_tree_zero=true` and `owner_closed=true`; supervisor return was exit 1 and scheduler deletion was performed only after preservation.

This is a separate import-stage failure from S241 status-gap and does not prove the transport repair caused it. The next review must compare the pinned import recipe and current workstation state before any fresh formal ID; do not change gate, timeout, profile, counter, RSS, or merge partial rows.

- raw manifest SHA256: `75437e7130c1b120e889af6712533dccd1acb1dbd3e14409a6b9c3a0db9ddcee`
- archive: `studio/.local/archives/gt06-s243-formal-01-s244-import-wall.zip`
- archive SHA256: `5260eee2e2f8ff1053974e2b9f7c43e12f2e8f9c9a0545f60cde3b90659e746c`
- raw/archive members: `159`
- authority: `0`; formal acceptance: `false`
