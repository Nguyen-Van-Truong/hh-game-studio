# Release checklist — R9-WP4 operations handoff

Unsigned **internal** package only. Public upload / name / trademark / signing /
channel is **E3**. The agent does not upload. Do not invent a cert, an API key,
or a Hyper-V. `--provider plan` stays.

This machine is **not** a clean VM. `CLEAN_VM` stays unproven. `not_g6=1`.
Do not copy an exe into a folder named `clean-vm` and stamp proven.
Do not tick G6 or GX.

## What a reviewer receives

| Piece | Where |
|-------|--------|
| Studio bundle | `python tools/godot/package.py --out %LOCALAPPDATA%\HHGodotAgent\packages\hh-godot-agent` |
| Checksums / SBOM / NOTICE | bundle `checksums.txt`, `sbom.json`, `NOTICE.md`; game export `artifacts/r9-wp1-export/` |
| Install / doctor / rollback | [INSTALL.md](INSTALL.md) |
| Pin / upgrade | [COMPATIBILITY.md](COMPATIBILITY.md) — pin stays `4.7.1-stable` / `a13da4feb` |
| Ops runbooks | [OPERATIONS.md](OPERATIONS.md) |
| Evidence review | [EVIDENCE_REVIEW.md](EVIDENCE_REVIEW.md) |
| Known limitations | [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — mapped to the Capability Matrix |
| Gate catalog | `python tools/godot/ops.py catalog` |

## Internal checklist (agent / coordinator)

1. Kill leftover Godot first. One drill at a time. Sequential. No Superfighter folder.
2. Package exact addon/sidecar/launcher. No `npx -y`. No online-latest. No 4.7.2.
3. Verify checksums. Tamper must reject (Observe/Doctor only).
4. Current-user install. No admin. User project stays outside the install root.
5. Run the disaster drill in [OPERATIONS.md](OPERATIONS.md).
6. Review security / privacy / license / SBOM / autonomy / dogfood evidence.
7. Confirm `CLEAN_VM=unproven`. This Godot/Node/source OS is not AC-20.
8. **STOP** before publish / sign / store / trademark / channel — human E3.

## STOP — E3 (human only)

Do **not** do these from the agent:

- invent a `.pfx` / signing cert
- upload to itch / Steam / GitHub Release / a public channel
- send telemetry or package bytes off-box
- pick a public product name / trademark
- tick G6 because a smoke folder looked empty

After a **real** clean VM (no Node, no Godot, no source on that OS) proves
AC-20/AC-21/AC-22, a coordinator+critic may tick G6. Public release still
needs a separate E3 approval.

## Official verify

```text
python tests/bootstrap/test_release_handoff.py
```

Labels: EVIDENCE, RUNBOOK, DRILL, REVIEWER, GATES, CLEAN_VM.
RUNBOOK may be proven. EVIDENCE stays unproven. DRILL stays unproven.
REVIEWER stays unproven. GATES stays unproven while G6 is unresolved.
`CLEAN_VM` stays unproven. `not_g6=1`. G6 stays `[ ]`. GX stays `[ ]`.
CLEAN_VM stays unproven. --provider plan stays.
