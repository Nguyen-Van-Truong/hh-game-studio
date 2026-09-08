# Coordinator notes — split S1, design only

Owner correction: exactly two active TXT plans, Godot/Blender/agent tools
first, HH World gameplay and Vietnam integration second. New plans were
created via Set-Content headers then multiple bounded Add-Content sections;
focused edits corrected dependencies/ownership and stale section references.

- Tools: 10 GT, fixture owns its source under studio/** and needs no H2.
- Game: 32 H2, H2-P0-01 consumes GT-10; H2-P1-01 verifies integration,
  H2-P2-04 verifies actual Blender-to-game Solo workflow. Tools acceptance
  remains fixture conformance; game quality/economy/WAN/people remain separate.
- Legacy ST IDs only in tools historical mapping, never active WP table.
- 14 TX tooling cases and 36 EX game cases; 45 dependency edges; single cross
  edge GT-10 -> H2-P0-01. No duplicate deliverable acceptance or cycle.
- New pin is candidate until official artifact verification, no install/fork
  or global VF pin changes. Game content/API/runtime source untouched.
- Old unified body preserved byte-for-byte after archive header; hash checked
  against unified-archive.json. Historic U2 freeze applies pre-archive only.
- Scoped AGENTS/CLAUDE/START/PROGRESS and historic01–09/oldmasters route to
  these two plans. Root VF governance and social services remain unchanged.

Static validator initially had a PowerShell arithmetic expression grouping
error, fixed in validator only. It then detected that the manifest builder's
Sort-Object on OrderedDictionary entries did not sort declared paths. Corrected
manifest ordering by sorting parsed records; all18 file hashes stayed unchanged.
freeze-s1-initial.json preserves the initial metadata; freeze-s1.json records
correction from168431567a47ece366d8a0b24566a7a5497558f51045112d47eaed02379341ef
to458124251764e1cabc6dcf540579fdd74c66ce01065788c4afd06c3c36b99336.
The two TXT contents did not change during this metadata correction.

static-s1.json now PASS_STATIC_ONLY:18source files,42WP/42spec,50exceptions,
51local links,45edges and capacity arithmetic. No runtime/independent review
acceptance follows from these checks. git diff --check scoped docs passes;
line-ending conversion notices are Git normalization warnings, not errors.

No commit/stage: documents span two repos and unrelated owner changes remain
in social working tree. No automation, server/game run, model substitution,
new benchmark claim or signed human acceptance in this planning task.
