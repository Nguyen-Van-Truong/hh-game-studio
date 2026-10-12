# GT-10-PC coordinator acceptance — gt10pc-rehearsal-20261012-c3h (owner decision O14)

Date: 2026-10-12 14:42 Asia/Saigon
Basis: owner O14 (12-10 14:05: short checks only, skip the 10×35 soak and the long final, PC first)
and O14.7 (12-10 14:17: subagents and both critics run on grok-4.7-xhigh).
This is not a soak PASS and not a FINAL matrix. The package keeps its `REHEARSAL_PASS` labels,
`authority` 0 and `acceptance` false; this file is the coordinator decision on top of it.

Run: `gt10pc-rehearsal-20261012-c3h`
Source freeze commit: `744a9f61`
(`git diff --stat 744a9f61 HEAD -- 8-9-hh3d-3/studio` was empty for both critic reviews)
Task studio closure (request.json, return.json):
`sha256:86dc9f1cb8fa2e6dc9005d8e4ba2031f4c1862aa930d7287ae9db0077d7724bd`
Package source closure (matrix.json, release manifests):
`a6280d76c7059d3e1b11aabf6486fe63c00068a19ab8f3c525a569533906da3b`
Windows 0.1.0 manifest SHA256:
`3bb561df55ce31b372447be2a9c7bb9e9a8da4c6655f08db176c266db632b595`
Trust store `studio/.local/gt10pc-publisher-v2/trust.json`, SHA256:
`2d19e3e90a719ead39cd1874193f90f98e9f8b2e2b71fb9d0ea451c7336af2e0`
Artifacts (machine-local, not in git):
`studio/.local/reviews/gt10pc-rehearsal-20261012-c3h/artifacts/{windows,linux}/{release,upgrade}.hhpkg`

## Gate evidence

- Scheduled Task `\HHStudio.GT10PC.gt10pc-rehearsal-20261012-c3h`: `returned_exit_code` 0 after
  1276.5 s, `actual_process_exit_observed` true, `task-terminal.json` `last_task_result` 0,
  `task-deleted.json` present, task stderr empty.
- Coordinator `--verify-only` at 14:25:42 (about 45 s): process exit 0, `status` `RAW_VERIFIED`,
  `errors` {}, mode REHEARSAL. Both critics re-ran the same command and saw the same result.
- Coordinator read-only checks at 14:41 (`coordinator-unsure-check.json`, closes critic B's UNSURE):
  - All four archives list 809 members each, with 0 members under a `zdoc`, `reviews`, `.local`,
    `.godot`, `.git` or `__pycache__` path segment, and no `.raw` member. The only "private" names
    are the source modules `host/core/private_{events,store}.py`, their docs and tests.
  - All 39 files in `gt06-p11-short-ad57e858/source-files.json` match the frozen tree byte for byte.
- Coordinator raw reads before the critics: P11 `import-host/process-exit.json` pid 37680 exit 0 and
  `editor-host/process-exit.json` pid 20620 exit 0 equal `capture.json` `actual_exits`; P4 parent
  hosts `children/windows-producer-host.json` pid 7580 and `linux/host/run-host.json` pid 28892 exit 0.
- Source-drift check after the status edit in this acceptance commit: see the last section.

## P1–P12

| Row | Result | Evidence (recomputed by `verify_raw_rows` unless noted) |
| --- | --- | --- |
| P1 | PASS | Four archives, 809 members each; payment, monetization and armed failpoint counts 0; no zdoc/reviews member (coordinator listing). |
| P2 | PASS | Eight archive attacks re-run through `verify_package`; native rejection child pid 43928 exit 0 with equal before/after install, project and state ledgers. |
| P3 | PASS | Windows producer pid 7580 and Linux docker run-host pid 28892, exit 0; both fixtures installed into clean copies, roundtrip and Play read back. |
| P4 | PASS | Upgrade 0.1.0 → 0.1.1 and rollback with Play on both platforms; refusals `unsupported package schema` and `untrusted signing key` recomputed from package bytes and unchanged selectors (`P4_NEG_VERIFIED` both sides). |
| P5 | PASS | Uninstall keeps art, game, source and save; reinstall checked (Windows receipt and ledger, Linux reinstall phase, lifecycle 8). |
| P6 | PASS | Profile `hh-godot-gameplay-source-1` kept across install, upgrade and rollback; other projects have no profile. |
| P7 | PASS | Eight native cases in groups a/b/c (3+3+2); killers 44912, 9076, 16784 bound to group hosts, victims bound to `cut.json`, second retry unchanged, NOT_APPLICABLE reasons present. |
| P8 | PASS | Five host cases (missing-dependency, missing-template, addon-version, archive, closure) replayed against `observation.json`. |
| P9 | PASS | Independent consumer child pid 40832 exit 0; known-limit terms enforced; support bundle allowlist checked. |
| P10 | PASS | Installed copies: L01 pid 10, L02 pid 28, container 1284, W02 9360, W03 34192, K10 arena 273 and room 283, all exit 0; registered and publication hosts 29004 and 37044 exit 0, `readback_ack` true. |
| P11 | PASS (O14 short) | One real Godot cycle `gt06-p11-short-ad57e858`: child host pid 5856 exit 0, import 37680 and editor 20620 exit 0. The 10×35 soak is waived by O14.1. |
| P12 | PASS | Two independent grok-4.7-xhigh critics on the same hashes, both `TICK=yes`, no BLOCKER or MAJOR. |

## Independent critics (O14.7)

1. `critic-a-grok.md`, grok-4.7-xhigh, `TICK=yes`, SHA256
   `f7542bf29ecec6473446f217ab45f837ec13e39e6d0170d7221b56b57061971f`.
2. `critic-b-grok.md`, grok-4.7-xhigh, `TICK=yes`, SHA256
   `d28bec69501c0bc4b137d1bc960fc853df8a421f74c4060b301d5546a8933808`.

Disclosed and not counted: `critic-b-sol.md` (GPT-5.6 Sol, SHA256
`c5851da05091da4495bf5d00d22abdd6a8ed30a9e4552d2ddb56d53c03f3b13e`). The owner stopped that run at
14:17 (O14.7) after it wrote `TICK=no` with two MAJORs:
1. The P4 refusals have no per-case host receipt.
2. The P11 short-row Godot exits are not bound to `process-exit.json`.

Coordinator assessment: both are gaps in how the verifier binds evidence, not functional failures.
The raw agrees: P11 `process-exit.json` gives 37680/0 and 20620/0, and the P4 parent hosts exit 0
while the refusals are recomputed. Both Grok critics list the same two points as MINOR. They are
recorded below as known limits and as the first tool-fix candidates (G1, G2).

## Known limits accepted with this decision (O14.3)

- No long-session measurement: memory, handle and object growth over many sessions is unknown;
  upgrade and rollback were exercised only in short sessions.
- G1: `_verify_p11_short_row` reads Godot exits from `capture.json`, not `process-exit.json`.
- G2: P4 refusals run in-process inside the producers; no per-case host receipt.
- Native P2 trusts `rejected: true` (ledgers and child host are recomputed). The P1 scan has no
  zdoc/reviews segment rule of its own (the coordinator listing found none). Windows reinstall is a
  receipt and ledger check without another Play.
- Local test key only; no public release channel. Revocation, expiry, security floor and key loss
  belong to full GT-10.
- Android: GT-08B stays `DEFERRED_OWNER_NO_ANDROID`; full GT-10 waits for it.
- Re-verifying c3h needs the packaged studio files as of `744a9f61`. A later change to any packaged
  file (for example under `host/`, `godot-addon/`, `package/` or `tests/`) makes `--verify-only`
  report `DIAGNOSTIC_SOURCE_DRIFT` with exit 2 by design. Root docs such as
  `studio/AUTHORING_STATUS.md` are not packaged and do not drift it (last section).

## Decision

**GT-10-PC ACCEPTED under O14 (short checks), 2026-10-12.**
The PC tools plan is complete: GT-01..GT-09 and GT-10-PC. GT-11 opens only from a game change
request (first candidates: Superagent SA-T01..SA-T06 and the verifier gaps G1, G2).
Usage guide for game agents: `zdoc/12-10-huong-dan-dung-cong-cu-godot-blender.txt`.
Do not claim a soak PASS, a FINAL matrix, Android, a public channel, a finished game or Y8 parity.

## Source-drift check after the status edit

`studio/AUTHORING_STATUS.md` was rewritten for this acceptance, then the same `--verify-only`
command ran again: end 14:46:37, 85 s, exit 0, `status` `RAW_VERIFIED`, `errors` {}, no `findings`,
stderr empty. The file is not an archive member (the `payload/studio/` root holds only
`toolchain.lock.json`), so the drift branch was again not taken. Critic A's UNSURE about that
branch stays open; critic B read it in code (`gt10pc_matrix_verify.py:117-123`).
