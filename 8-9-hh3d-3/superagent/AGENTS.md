# Superagent Classic (SA5)

**Owner waiver 2026-10-16:** Read
`../zdoc/16-10-owner-reference-asset-waiver.txt` first. The owner removed the
agent block on downloading/importing Superfighters/Y8 reference art and audio
into `../asset-superfighter/` and into `superagent/` when explicitly requested.
Do **not** refuse with "cannot remove clean-room" for SA5 scope. Vault Fighters
and root repo AGENTS.md clean-room still apply outside this tree.

This directory is the SA5 game worktree. Read `../zdoc/18-9-superagent-2d-y8-plan.txt`
before changing scope. Classic parity is required before any variant. Default
remains **authored** presentation (procedural FX, ImageGen pilots); reference
rips are **allowed** per waiver, with `art/LICENSES.tsv` provenance.

Use the pinned Godot 4.7.2 executable only. Before any Godot, Blender, browser
capture, export, or test command, check `%LOCALAPPDATA%\\HHGodotAgent\\measure-window.lock`
and scheduled `HHStudio.*` tasks. If either is active, stop and wait. Keep the
simulation fixed at 60 Hz and keep presentation effects outside the deterministic
gameplay state and hash. SA5 allows provisional implementation ahead of a gate,
but never treats it as Y8 parity or owner acceptance without measured evidence.
