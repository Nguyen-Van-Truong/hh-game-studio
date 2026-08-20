# Threat model — HH Godot Agent (R0-WP4 baseline)

Scope: the **intended** control plane (TypeScript sidecar + GDScript EditorPlugin +
localhost session). This is a paper baseline so R1 cannot enable a third-party MCP
plugin without mapping each threat to a control. Runtime enforcement lands in R2
(`addons/hh_agent` + bridge policy engine). Invariants: **A8, A9, A10**
(`zdocs/20-8-godot-agent-autopilot-plan.txt` §3, §0.4, §6.4).

Owner profile: **OWNER_AUTOPILOT** may mutate the project without per-command
approval. It does **not** grant off-project shell, spend, publish, or skipped
checkpoints. **Pause** always wins (A14).

Controls used below:

| Control | Meaning |
|---------|---------|
| **reject** | Fail closed: no ACK, no mutation, typed error (`E_DENIED` / `E_JAIL` / `E_SECRET`). |
| **jail** | Canonicalize; only allowlisted roots; block `..`, symlink/junction escape, device paths. |
| **strip** | Remove or disable debug/runtime-bridge code and secrets from **release** export. |
| **Pause** | Close the mutation gate, drain/rollback in-flight atomic commands, keep recovery checkpoints. |

---

## T1 — Token theft

**Story.** The session token (256-bit, A9) leaks via log, screenshot, MCP resource,
git, a copied `policy.toml`, or a tool that echoes headers. Attacker on the same
machine (or a malicious `@tool` script) replays the token and mutates the project.

**Why it matters.** OWNER_AUTOPILOT would treat the thief as the owner.

**Controls**

- **reject:** non-loopback bind; missing/wrong token; `log_secrets = true`; committed
  `sk-` / `ghp_` / `token=<high-entropy>` shaped values (validator + Git scan).
- **jail:** token only in `%LOCALAPPDATA%/HHGodotAgent/` with current-user ACL; plugin
  connects outbound to the sidecar using the session descriptor — no fixed-port scan
  (plan §2.2). HTTP Origin check if HTTP is ever used.
- **strip:** redact token, home path, and env secrets from logs/screenshots/events
  (§6.4).
- **Pause:** owner hits Pause after suspected leak; gate ACKs draining; rotate the
  session token (R2) before resume.

**Invariant:** A9 (loopback + random token + ACL, never log secrets).

---

## T2 — Malicious project / `@tool` script

**Story.** The opened Godot project ships a hostile `EditorPlugin` or `@tool` script
that runs on the editor main thread: writes outside `res://`, reads the session file,
or calls into the hh_agent plugin.

**Why it matters.** Editor plugins are code execution in the owner's Godot process.

**Controls**

- **reject:** generic write/delete tools cannot touch `res://addons/**` (the
  Godot project addon host, including a third-party MCP plugin),
  `godot/plugin-project/addons/**` (same host on disk), `addons/hh_agent/**`,
  `.hh-agent/policy.toml`, capability-lock, or the ledger (§6.4).
  `allow_write_rel = ["godot/"]` does not punch through those deny prefixes;
  `res://`, `./`, `//`, and case-folded spellings are the same paths.
  Unknown eval / `Object.call` surfaces from the agent tool list are denied (see T4).
- **jail:** project-content mutation stays under project root after canonicalize (A8).
  Import goes through magic/size/decode + quarantine before `res://`.
- **strip:** do not vendor un-audited addons into `plugin-project` (R1 bake-off is
  disposable copies). Release export must not include editor plugins or evidence.
- **Pause:** if a `@tool` script misbehaves, Pause stops **agent** mutations; the
  owner can disable the plugin / revert the last Git checkpoint (A10).

**Invariant:** A8 (root jail), A10 (checkpoint before destructive), A7 (Godot objects
on main thread — hostile scripts are why we do not expose shell/eval).

---

## T3 — Path escape (`..` / symlink / junction)

**Story.** A command path is `res://../.ssh/id_rsa`, `godot/../../Windows`, a symlink
to `%LOCALAPPDATA%`, or a Windows **junction** to another volume.

**Why it matters.** OWNER_AUTOPILOT plus a path bug is arbitrary filesystem write.

**Controls**

- **reject:** any path whose components include `..`; OS-absolute paths outside the
  tiny allowlist (`%LOCALAPPDATA%/HHGodotAgent` for session/ledger, explicit export
  `out_dir` grant, read-only import source then copy to staging). Device/reserved
  names and over-long paths (A8).
- **jail:** canonicalize (resolve `.` / case / `\\?\`) then verify the result is
  still inside the granted root; **refuse** symlink and junction escape (do not
  follow a link out of jail). Policy flags `block_dotdot`, `block_symlink_escape`,
  `block_junction_escape` are required true.
- **strip:** n/a (this is an editor/sidecar write path, not export).
- **Pause:** on jail violation, fail the command and Pause the mutation lane rather
  than “repair” by writing elsewhere.

**Invariant:** A8.

---

## T4 — Arbitrary `eval` / `Object.call`

**Story.** An MCP tool takes a GDScript snippet or a `method` + `args` blob and
executes it in the editor (`Expression`, `Object.callv`, `OS.execute`, `shell`).

**Why it matters.** That bypasses the semantic command schema, UndoRedo, and the
process allowlist.

**Controls**

- **reject:** no arbitrary shell tool; no generic eval/`Object.call` in the plugin
  surface (A9). Subprocess **args are arrays**, never concatenated shell strings
  (§6.4). Process allowlist is only **Godot pin, GUT, exporter, Git**.
- **jail:** even Git/Godot child processes get cwd + path arguments jailed to the
  project or doctor cache.
- **strip:** n/a at rest; if a candidate MCP exposes eval, R1 marks it fail-hard
  for OWNER_AUTOPILOT (plan R1-WP2 checklist).
- **Pause:** if a command is already in flight, Pause lets atomic UndoRedo finish
  or roll back; it does not run a follow-up eval to “clean up”.

**Invariant:** A9 (no arbitrary shell/eval via plugin), A2 (semantic source of truth).

---

## T5 — Dependency supply chain

**Story.** `npx -y latest`, Asset Library “latest”, an unpinned MCP clone, or a
compromised Godot/GUT/Node tarball runs in the editor or sidecar.

**Why it matters.** OWNER_AUTOPILOT would execute the attacker’s plugin as the owner.

**Controls**

- **reject:** GitHub `/releases/latest`, `npx -y latest`, Godot 4.7.2* / 4.8*, Mono
  builds (doctor refuse list). Non-MIT MCP **Full**/commercial trees if they would
  be required for core acceptance (E2 + license).
- **jail:** vendor only under `third_party/` at an exact commit (R1-WP2+); do not
  clone candidates in R0.
- **strip:** SBOM + LICENSE/NOTICE on release (A16); checksum pin in
  `docs/VERSIONS_GODOT.md` / `tools/godot/pin.json`.
- **Pause:** on checksum or license mismatch, do not enable the plugin; stop the
  mutation lane until the pin is restored.

**Invariant:** A16 (exact version/hash + SBOM). See [SBOM_BASELINE.md](SBOM_BASELINE.md).

---

## T6 — Runtime bridge leaking into **release** export

**Story.** `HHAgentRuntime` autoload, debugger hooks, MCP ports, session tokens, or
`.hh-agent/evidence` ship inside the Windows game build. A player then talks to the
agent bridge or reads secrets.

**Why it matters.** Play is a **separate process** (A11). Release players are not
owners. A leftover runtime is remote control of the shipped game.

**Controls**

- **reject:** export preset that includes `addons/hh_agent`, sidecar, tokens,
  evidence, or test runtime (§6.4 artifact scan).
- **jail:** runtime observation APIs exist only in editor/debug/test builds;
  production autoload is not registered.
- **strip:** debug/test-only runtime code is compiled out or feature-flagged off
  for release; filter export resources; scan the packed artifact.
- **Pause:** does not apply at player runtime; if an export job is running when
  Pause hits, stop at a safe-point and **do not** ship a partial pack (A14).

**Invariant:** A11 (Play ≠ editor), A9 (token not in the game), §6.4 strip/scan.

---

## Mapping summary

| Threat | reject | jail | strip | Pause |
|--------|:------:|:----:|:-----:|:-----:|
| T1 Token theft | ✓ | ✓ LocalAppData + loopback | ✓ redact | ✓ rotate after Pause |
| T2 Malicious `@tool` / project | ✓ lock plugin/policy | ✓ A8 root | ✓ no unaudited addon in export | ✓ checkpoint / disable |
| T3 Path escape | ✓ `..` / abs | ✓ canonicalize + no follow | — | ✓ fail closed |
| T4 eval / `Object.call` / shell | ✓ allowlist | ✓ child cwd | R1 fail-hard if candidate has it | ✓ no cleanup-eval |
| T5 Supply chain | ✓ pin / no latest | ✓ `third_party/` later | ✓ SBOM | ✓ do not enable |
| T6 Runtime in release | ✓ export scan | ✓ debug-only APIs | ✓ strip autoload | ✓ cancel export safe-point |

E1–E4 remain owner stop-gates and are **not** substitutes for the table above.
A stolen token is T1, not E1. Buying a commercial MCP is E2 **and** T5.
