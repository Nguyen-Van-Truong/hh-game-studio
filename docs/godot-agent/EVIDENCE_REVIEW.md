# Evidence review — R9-WP4

Security / privacy / license / SBOM / clean-VM / autonomy / dogfood.
This is a paper catalog of existing artifacts, not a new game and not a
G6 tick. Heading-only sections are not a re-run of scan / SBOM / privacy /
VM review. EVIDENCE stays unproven.

`--provider plan` stays. Do not invent an API key. Do not invent Hyper-V.
`CLEAN_VM` stays unproven. `not_g6=1`. GX stays locked. Superfighter is
not started.

## Security

| Control | Evidence | Honest status |
|---------|----------|----------------|
| Root jail / path allowlist (A8) | [THREAT_MODEL.md](THREAT_MODEL.md), `tests/bootstrap/test_policy.py` | Proven for policy fixtures |
| Loopback + token, never log secret (A9) | session in `%LOCALAPPDATA%/HHGodotAgent/`, `test_no_secrets.py`, doctor `token_redacted` | Proven for sidecar/doctor; leftover session files are a known R9-WP3 residual |
| Checkpoint before destructive (A10) | `test_git_checkpoint.py`, Review Center revert | Proven for named checkpoint actions |
| Pause wins (A14) | G4 soak / zero-touch | Proven as mutation gate |
| Export strip addon/token/evidence | `tests/bootstrap/test_export_clean_build.py` SCAN | Proven on this machine |
| Tamper checksum reject | `tests/bootstrap/test_package_install.py` TAMPER | Proven on this machine (not a clean VM) |
| Process allowlist / no arbitrary shell | `.hh-agent/policy.example.toml` | Paper + validator; hashes of binaries are not pinned |

Do not enable vendor MCP addons (`mcp_vendor=none`). Bake-off copies stay out
of `plugin-project`.

## Privacy

- Session token is a 256-bit CSPRNG hex, current-user ACL, not an API key.
- Tokens and logs stay under LocalAppData. They are not a git artifact.
- Collect-logs redacts token, profile/home paths, and credential-shaped prefixes.
- No product telemetry. E3 forbids sending package/game bytes off-box.
- Screenshots / evidence must not include the token (A9 / §6.4).

## License / SBOM

| Artifact | What it proves |
|----------|----------------|
| [SBOM_BASELINE.md](SBOM_BASELINE.md) | Godot 4.7.1-stable MIT, GUT 9.7.1 MIT, Node 24.19.0 MIT, TypeScript 5.9.3 Apache-2.0. Not a CycloneDX dump. |
| Bundle `sbom.json` / `NOTICE.md` | Unsigned studio package components |
| `artifacts/r9-wp1-export/sbom.json` | Kho Bi An export: Godot MIT, Open Sans OFL-1.1, no addon/sidecar |
| `docs/godot-agent/NOTICE` | In-house thin; vendor MCP source was not copied |

Godot trademark policy stays with the Foundation. Public name/channel is E3.

## Clean VM

**Unproven.** This OS has Godot, Node, and source. Official R9-WP1/2/3
smokes are not a VM. AC-20 (Windows clean VM export) is G6. Do not map a
LocalAppData folder named `clean-vm` to proven. `not_g6=1`.

## Autonomy (G4)

Gate G4 is signed. Official `tests/bootstrap/test_zero_touch.py` is the
90-command zero-touch proof. `--provider plan` is the keyword compiler + DAG,
not an LLM. Do not invent an API key to “make autonomy look smarter.”

## Dogfood (G5)

Gate G5 is a **human** accept (2026-08-26, “Chấp nhận — game đạt”) after play
of Kho Bi An against `godot/dogfood/kho-bi-an/REVIEW_RUBRIC.md`. Official
recreation PASS with `EXPORT=proven` and `RECREATE/HASHES/CRITIC/RUBRIC`
unproven (`not_g5=1` then human). This is not agent play. Superfighter is
queued after remaining plan WPs and is **not** started here.

## Gates / artifacts

`python tools/godot/ops.py catalog` must show G0–G5 resolved, G6 unresolved,
GX locked. See [RELEASE.md](RELEASE.md) and `tools/godot/release_gates.json`.
CLEAN_VM stays unproven. --provider plan stays.
