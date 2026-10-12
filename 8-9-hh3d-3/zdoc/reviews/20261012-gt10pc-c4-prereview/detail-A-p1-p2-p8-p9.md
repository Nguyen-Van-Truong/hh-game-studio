# GT-10-PC pre-review — P1, P2, P8, P9, host receipts

Package: `8-9-hh3d-3/studio/.local/reviews/gt10pc-rehearsal-20261012-c3e`
Judged against committed HEAD (`git show HEAD:8-9-hh3d-3/studio/tests/conformance/...`).
Working tree is uncommitted and was used only to see whether a gap is already being fixed.
Read-only. No Godot, Blender, Docker, matrix, or test suite was run.

Matrix label is `REHEARSAL_PASS`, `authority=0`, `acceptance=false`, schema `hh-gt10pc-matrix-3`.
That label is not treated as proof. The scheduled-task folder
`gt10pc-rehearsal-20261012-c3e-task` records the matrix process
(`return.json`: `returned_exit_code=0`, `actual_process_exit_observed=true`, ~1640 s).
It does not record per-row PIDs.

HEAD rehearsal verifier `run_gt10pc_matrix.py:_verify_rehearsal_matrix` (lines 377–398)
re-reads raw bytes only for P11 (`_verify_p11_short_row`). For P1, P2, P8, and P9 it
requires `rows[row].status == "REHEARSAL_PASS"` and nothing else.

WIP (not in c3e): `run_gt10pc_matrix.py:_verify_rehearsal_matrix` calls
`gt10pc_matrix_verify.py:verify_matrix` → `verify_raw_rows`, which re-opens archives
and several raw directories. `_p8_host_checks` now calls `gt10pc_p8_checks.run_p8`.
c3e was not produced by that WIP. Where WIP expects files c3e does not have, this
package still fails.

Archive bytes checked in memory from `artifacts/windows/release.hhpkg` and the other
three hhpkg files. SHA-256 matches `matrix.json` `artifacts`:

| file | sha256 |
| --- | --- |
| artifacts/windows/release.hhpkg | af6356e3a61dcf723222b5c8a47c1d5c592bc4619906dd5263f9acaa9e0fdbab |
| artifacts/windows/upgrade.hhpkg | ca1b09090748d9d1c62367ed4d9a7bf21104f252c5720070a172a772e6d665be |
| artifacts/linux/release.hhpkg | e804a3cc32fbd9834dcf5e2d82da090fb528dc9d2fdaac9207f23b11a7e7ecf9 |
| artifacts/linux/upgrade.hhpkg | 342bbfd66e5bb1938c4aae146d064498532023e0dfb463b415dfb11e6dfc7453 |

Each zip has 800 members. No member path contains `zdoc/` or `/reviews/`.
No `trust.json`, `private.raw`, or `gt10pc_signing.py`. `source_closure_sha256`
on all four manifests is `a90f378e10ecd6326e38b0cac39b5b4675ff4b71e3ecd2b5151cb3733d7e4f03`.

---

## P1 — package manifest and scans

**(1) Requirement.** HH-STUDIO-0.1 / P1: manifest id, version, target, artifact hashes,
closure, protocol/schema digest, toolchain lock, SBOM/license/notice, security floor,
trust key id, rollback compat; `supported_targets` Windows/Linux/Linux-headless and
`android=DEFERRED_NO_DEVICE`; scans on the archive bytes for no zdoc/reviews,
`monetization=OFF`, failpoints off; known limits, runbook, and help included.

**(2) Evidence in c3e.** The row itself is only
`matrix.json` `rows.P1 = {status, targets: [Windows, Linux-headless]}`.
The bytes are the four archives above. Windows 0.1.0 `manifest.json` inside the zip:

- schema `hh-studio-package-0.1`
- package_id `hh-studio-6de3339a459d4583f379cafcf181c74f1165fb3dc5ac05503fe1e8219b34f0e0`
- version `0.1.0`, target `Windows`
- supported_targets `["Windows","Linux","Linux-headless"]`
- android `DEFERRED_NO_DEVICE`
- content_sha256 `41bf127b9da11a266b7dfdf00e270bb37a84133778e20c6d0b35b1d0c32ede2b`
- source_closure_sha256 as above
- protocol_schema_digest `53f820edc283f405c28b10d484a33f2d2d155446fecf1143354071da657e25cf`
- toolchain_lock_sha256 `28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`
- trust_key_id `hh-local-test-007994db81f75757`
- security_floor `local-test-floor-1`
- rollback_compatibility `{schema: hh-studio-package-0.1, version_series: 0.1}`
- monetization `OFF`, failpoint `DISABLED`
- signature present (64-byte hex field; not copied here)

Same field set on the other three archives, with version/target/package_id/content hash
changing as expected. Docs inside every archive: `docs/NOTICE.txt`, `docs/SBOM.json`,
`docs/compatibility-lock.json`, `docs/known-limits.md`, `docs/requirements.txt`,
`docs/runbook.md`. SBOM schema `hh-file-sbom-1` lists runtime/verification components
and `cryptography` 46.0.5. NOTICE says source files keep their original licenses.
Apache-2.0 text is at `payload/studio/protocol/_rfc8785/LICENSE-APACHE-2.0`.
Toolchain member `payload/studio/toolchain.lock.json` pins Godot 4.7.2-stable,
commit `ed1daf0bf001b61586d9930840f2f1394092c079`, console/gui SHA-256, export
templates version+sha256, Blender 5.2.1 executable SHA-256, Python 3.11.9.
Compatibility lock: engine 4.7.2-stable, addon `hh_studio` 0.1.0,
`network_policy=offline-only`, `latest_autofetch=false`, android deferred.

Name scan of all 800 members: no `zdoc`, no `reviews/` directory. The 17 names
containing the substring `evidence` are source modules (for example
`gameplay_dependency_evidence.py`), not a reviews tree.
Content token scan of Windows release members: `monetization` occurs only in
`manifest.json` and `payload/studio/package/release_contract.py`. No member contains
`chargeback`, `voucher`, `refund`, `stripe`, or `payment sdk`.
Failpoint *code* ships: `payload/studio/host/core/gt07_failpoints.py` and its test.
No `gt07-failpoint.json` config is in the archive.

**(3) HEAD checks.**

- Producer: `run_gt10pc_matrix.py:run_rehearsal` (P1 branch, ~630–637) calls
  `release_contract.py:verify_package` on each of the four archive paths.
- `verify_package` reads the zip bytes, then `verify_manifest` checks the field set,
  signature, version, target, `supported_targets`, `android`, `monetization==OFF`,
  `failpoint==DISABLED`, security floor, rollback object, and digests.
- `verify_contents` checks closure, content hash, protocol/schema digest, toolchain
  lock bytes, and `docs/compatibility-lock.json` via `_verify_compatibility_lock`.
- `_safe_member` rejects names starting with `zdoc/`, `evidence/`, or
  `payload/studio/evidence/`. It does not reject `reviews`.
- Builder `build_package` copies known-limits, runbook, NOTICE, requirements, and
  the compatibility lock into `docs/` and writes the monetization/failpoint strings.
  It does not scan member text.
- Verifier: `_verify_rehearsal_matrix` does not open any hhpkg.

**(4) Gaps.**

- **BLOCKER.** Rehearsal verify accepts P1 from the status flag. A final that only
  re-runs HEAD `verify_only` does not recompute the manifest from `artifacts/`.
  Fix: verifier opens each hhpkg and checks manifest fields, ledger, and digests
  against the zip (WIP `verify_raw_rows` already calls `verify_package` on the four
  paths before the P1 branch). c3e’s archives would survive that call; the status-only
  HEAD verifier would not prove it.
- **BLOCKER.** Monetization and failpoint admission are manifest strings the builder
  writes, then `verify_manifest` reads back. There is no scan of member bytes for a
  payment SDK, voucher/refund/chargeback handler, monetization UI, or an armed
  failpoint (`MONETIZATION_POLICY=OFF_ARTIFACT_SCAN_REQUIRED`, plan GT-10). The
  Windows release bytes happen to lack those payment tokens, and the failpoint
  module is present but no arming config is packed. Fix: inside `verify_package`,
  scan member bytes (and reject an armed failpoint config) and fail closed. Record
  the scan result next to the archive hash. WIP does not add this scan.
- **MINOR.** `reviews/` is not an explicit denylist. c3e has no such member; a
  `payload/studio/.../reviews/...` file would pass `check_names`. Fix: reject any
  member whose path contains `zdoc` or `reviews` as a directory segment.

**(5) WIP.** `verify_raw_rows` re-runs `verify_package` on the four c3e archives and
would bind `archive_sha256` / `manifest_sha256` / closure. It still only asserts
`rows.P1.targets`. It does not add a content monetization/failpoint scan or a
`reviews/` denylist. Not addressed: the two BLOCKERs’ scan half; the status-only
half is addressed for a future verify, not by new c3e files.

Supported from the zip itself (not from the row flag): id/version/target, closure,
protocol/schema digest, toolchain lock, SBOM/NOTICE/license file, security floor,
trust key id, rollback compat, supported targets, android deferred, docs present,
no zdoc/reviews members.

---

## P2 — tamper / truncate / version / target before unpack

**(1) Requirement.** Local test key pinned outside the artifact. Tamper, truncate,
version mismatch, and target mismatch rejected before unpack. Install, project, and
state ledgers unchanged. Source not deleted. At least one native rejection
(`p2-native`, `children/p2-native-rejection-*`). Revoke, expiry, security floor, and
key-loss recovery are full GT-10 and must be named in the package known limits.

**(2) Evidence in c3e.**

Host attacks (both targets), files only, no exception text stored:

- `p2-attacks/Windows/{tamper,truncate,wrong-version,wrong-target}.hhpkg`
- `p2-attacks/Linux-headless/{tamper,truncate,wrong-version,wrong-target}.hhpkg`
- `matrix.json` `rows.P2.archive_and_native_attacks` entries are
  `{target, attack, rejected: true}` with no reason.

Native worker, host-recorded:

- `children/p2-native-rejection-host.json`: `target_pid` 36564, `exit_code` 0,
  started `2026-10-12T00:52:30Z`
- `children/p2-native-rejection-receipt.json`: same pid, `wrapper_pid` 5912,
  `wrapper_exit_code` 0, `tree_verified` true, `timed_out` false
- `children/p2-native-rejection-stdout.txt` (260 bytes), stderr empty
- `p2-native/p2.json` schema `hh-gt10pc-p2-native-rejection-1`

Native reasons in `p2-native/p2.json` (match `matrix.json`):

| attack | artifact sha256 | reason |
| --- | --- | --- |
| tamper | 3a55be2767ae177ac2b63c9be5dbb38ba57f471c2b5844d10b15fd9345771707 | PackageError: package unreadable |
| truncate | a971e95bffe57109336178c9fdf17388e1d09943ed95c48c288512070e987915 | PackageError: package unreadable |
| wrong-target | e804a3cc32fbd9834dcf5e2d82da090fb528dc9d2fdaac9207f23b11a7e7ecf9 | PackageError: package target rejected |
| wrong-version | af6356e3a61dcf723222b5c8a47c1d5c592bc4619906dd5263f9acaa9e0fdbab | PackageError: package version rejected |

Byte check (this audit, not the producer flag): Windows tamper flips the middle
byte; truncate is 19 bytes shorter than `artifacts/windows/release.hhpkg`;
`p2-native/wrong-version.hhpkg` is a byte copy of the Windows 0.1.0 archive;
`p2-native/wrong-target.hhpkg` is a byte copy of the Linux-headless 0.1.0 archive
(sha `e804a3cc…`). Those two are real target/version mismatches at the install
API (`expected_version=0.1.1` on a 0.1.0 archive; Linux package installed as Windows).

Ledgers, byte-identical before/after (this audit):

- `p2-native/install-before.json` == `install-after.json` (192700 bytes, sha256 prefix `42c19c1909b18440`)
- `p2-native/project-before.json` == `project-after.json` (2105 bytes, prefix `741e3c467859066a`)
- `p2-native/state-before.json` == `state-after.json` (2258 bytes, prefix `5a7748ab0e981230`)

`p2.json` `last_good_active` is `85546002a7086f5a7e0e44edead5e0ecc7babcc70253e4d6481a8ccc54068e5b`
(Windows release manifest hash). Trust paths in the child argv are
`studio/.local/gt10pc-publisher-v2/trust.json` and `private.raw`, outside the hhpkg.
The archive does not contain those files. Known-limits text inside the zip is quoted
under gaps.

Nested after the rejections: `p2-native/driver/driver-host.json` pid 43000 exit 0;
`p2-native/native/godot-host.json` pid 5332 exit 0; `p2-native/native/parse-host.json`
pid 44776 exit 0; `p2-native/native/godot-stdout.txt` is a Godot log. These show
last-good still runs; they are not the rejection itself.

**(3) HEAD checks.**

- `run_gt10pc_matrix.py:_p2_archive_attacks` (490–586): mutates copies, calls
  `verify_package`, and on any `ValueError`/`OSError` appends `{rejected: true}`
  without storing the exception. Then `run_process` launches
  `gt10pc_p2_native_rejection.py` and writes
  `children/p2-native-rejection-receipt.json`.
- `gt10pc_p2_native_rejection.py:main`: `ConsumerInstall.install` per attack.
  `consumer_install.py:install` calls `verify_package` before `_stage`.
  `verify_package` rejects tamper/truncate at `ZipFile` (`package unreadable`)
  and rejects version/target in `verify_manifest` before the payload-member loop.
  After each rejection the worker compares install tree, project ledger, and
  state snapshot to the baseline.
- Production-time, `_p2_archive_attacks` re-reads evidence hashes and requires
  before/after JSON equality, attack names, and the Godot readback.
- Rehearsal verifier does not open `p2-attacks/`, `p2-native/`, or `children/`.

**(4) Gaps.**

- **BLOCKER.** HEAD `_verify_rehearsal_matrix` does not re-read attack bytes,
  reasons, ledgers, or `children/p2-native-rejection-host.json`. The host-attack
  loop also treats every exception as success and stores no reason. The native
  raw files do show the four reasons and unchanged ledgers; the verifier never
  looks at them. Fix: re-hash `p2-attacks/*` and `p2-native/*` against `p2.json`,
  require the four reason strings, require before==after ledgers, and require
  the children host pid/exit to match the receipt (WIP `verify_raw_rows` P2 branch
  plus `_verify_p2_native` does this). c3e’s native files would support that
  re-check; do not accept the row from `rejected: true` alone.
- **MAJOR.** `docs/known-limits.md` (same text in all four archives) says public
  key rotation, revocation, and expiry belong to the full release channel. It does
  not name security-floor policy or recovery when the trust key is lost. The word
  “loss” in that file is Windows power-loss durability, which is a different limit.
  Fix: add those two deferred items to `studio/package/known-limits.md` and rebuild
  so the archive member changes. WIP does not edit that file.

Not a gap: trust key is outside the artifact; native rejection is before disk
staging; install/project/state bytes are unchanged; source ledger is unchanged;
children host receipt exists for the native worker.

**(5) WIP.** Attack re-verify and `_verify_p2_native` address the BLOCKER for a
re-run of verify against these files. Known-limit wording is not addressed.

---

## P8 — actionable dependency / template / addon errors

**(1) Requirement.** Missing dependency, missing template, or addon version mismatch
returns an actionable error. No automatic `latest`. Artifact and closure are
verified before install. Question: does P8 call `gt10pc_p8_checks.py` and the older
GT-08A checker under `studio/build/ci/`, or only a subset?

**(2) Evidence in c3e.** There is no `p8-host/` directory and no per-case
`observation.json`. The only record is `matrix.json` `rows.P8`:

- `closure_verified: true`
- `network_used: false`
- `latest_autofetch: false`
- `missing_dependency_rejected: true`
- `missing_dependency_reason`: `missing dependency godot; provide the exact local godot 4.7.2-stable from toolchain.lock.json; latest/network auto-fetch is disabled`
- `version_rejected: true`
- `version_reason`: `package version rejected`
- artifact sha `af6356e3…`, closure `a90f378e…`

That missing-dependency sentence matches `consumer_support.py:verify_local_dependencies`
for godot 4.7.2-stable. `version_reason` matches `verify_manifest` when
`expected_version` is `0.1.1` on the 0.1.0 archive. It is not an addon mismatch.
No template case, no addon `plugin.cfg`, no proof that an install directory was
absent, no network-attempt log.

**(3) HEAD checks.** `run_gt10pc_matrix.py:_p8_host_checks` (124–148):

- calls `verify_package` once, then sets `closure_verified`, `network_used`, and
  `latest_autofetch` to constants
- calls `consumer_support.preflight(..., required=("godot",))` with no paths
- calls `verify_package(..., expected_version="0.1.1")` and looks for the substring
  `package version rejected`
- does not call `gt10pc_p8_checks.run_p8` or `verify_p8`
- does not call `studio/build/ci/gt08a_matrix.py`

`gt10pc_p8_checks.py` (HEAD, unused by the matrix) cases are
`missing-dependency`, `missing-template`, `addon-version`, `archive`, `closure`.
`exercise` goes through `consumer_support.install_checked` (verify, then install),
requires the repair text `latest/network auto-fetch is disabled`, and asserts the
install directory was not created. `verify_p8` replays each case and compares
`observation.json` to the replay. None of that output is in c3e.

`build/ci/gt08a_matrix.py:offline_rows` stamps N03 `wrong template` and N04
`unsupported addon` as `{status: PASS, rejected: true, reason: ...}` without
reading a template or an addon. Calling it would not be a real checker. P8 does
not call it anyway.

Rehearsal verifier checks only `rows.P8.status`.

**(4) Gaps.**

- **BLOCKER.** c3e P8 is a subset, and three of its booleans are constants written
  by the producer. Missing template and addon version mismatch were not run.
  Artifact/closure-before-install is not shown as an aborted install (no
  `p8-host/<case>/observation.json`, no absent install root). The package-version
  rejection duplicates P2; it is not the addon check. The implementer’s statement
  matches HEAD: the matrix does not call the full checker. Fix: `_p8_host_checks`
  must call `gt10pc_p8_checks.run_p8` / `verify_p8`, keep `p8-host/` (five cases,
  input bytes, reasons, `install` absent, network guard), and the verifier must
  replay those files. Do not call `gt08a_matrix.offline_rows` as a substitute;
  replace those canned N03/N04 rows if GT-08A is still cited. A final cannot
  accept c3e’s P8 object.
- **MINOR.** Even the real godot-missing sentence lives only inside `matrix.json`,
  which the producer writes. Fix: the observation file is the evidence; the matrix
  row should point at its hash.

**(5) WIP.** Working-tree `_p8_host_checks` now calls `run_p8(output / "p8-host")`
and `verify_raw_rows` calls `verify_p8` on `p8-host`. That is the right fix, and
it is not what produced c3e: `p8-host/` is absent, so this package still fails P8.
WIP does not invoke `gt08a_matrix.py`.

---

## P9 — handoff and independent consumer smoke

**(1) Requirement.** Compatibility lock, support runbook, known limits (journal and
the K13-class limits), support bundle scrubbed of secrets, and one independent
consumer that installs from the archive and runs a smoke. Is the consumer
independent of producer state, is the smoke a real Godot run, and is there a
host-recorded receipt?

**(2) Evidence in c3e.** `matrix.json` `rows.P9` is
`{status, evidence_kind: docs+native, artifact_sha256 af6356e3…, report_sha256
cc747912b2a3b6b6251618789b7a8ad7eb40ff2c52f9e745fee7c60ad9ffc074}` with no pid.

Docs are inside the archive (see P1) and again under the install tree
`p9-consumer/install/releases/85546002…/docs/` (`compatibility-lock.json`,
`runbook.md`, `known-limits.md`, `SBOM.json`, `NOTICE.txt`, `requirements.txt`).

Consumer tree `p9-consumer/`:

- `p9.json` schema `hh-gt10pc-p9-consumer-1`, fixture `gt09-arena` only
- `install-receipt.json`: action install, command_id `p9.independent-consumer.install`,
  status `COMMITTED`, active `85546002…`, version 0.1.0, closure `a90f378e…`
- `project-before.json`, `project-installed.json`, `project-after.json`
  (installed == after, both sha256 `0ba0a250…` in `p9.json`)
- `state-before-play.json` == `state-after-play.json` (`76b63880…`)
- `support.json`: schema `hh-studio-support-bundle-1`, `scrub_policy`
  `allowlist-no-raw-values-v1`. Keys are schema, authority, acceptance, scrub policy,
  package id/version/target/schema/closure, artifact and manifest hashes,
  `network_used`, and install counters. Command id is a sha256, not the raw id.
  No path, token, env, or source body.

Smoke processes (wrapper host files, not `children/`):

- `p9-consumer/drivers/gt09-arena/driver-host.json`: pid 21480, exit 0
- `p9-consumer/drivers/gt09-arena/receipt.json`: same pid, wrapper_pid 33104,
  `tree_verified` true; stdout is the probe’s one-line JSON, not Godot
- `p9-consumer/godot/gt09-arena/parse-host.json`: pid 29160, exit 0
  (`--check-only` on `res://addons/hh_studio/plugin.gd`)
- `p9-consumer/godot/gt09-arena/godot-host.json`: pid 18804, exit 0
- `p9-consumer/godot/gt09-arena/godot-stdout.txt`: first line
  `Godot Engine v4.7.2.stable.official.ed1daf0bf`, then
  `HH_FIXTURE_LIFECYCLE_*` through quit. Summary `mode=smoke`, `seed=90127`,
  `lifecycle_complete=true`, `reason=input_quit`
- `p9-consumer/godot/gt09-arena/receipt.json` `process.target_pid` is 18804, matching
  the host file. `studio` points at
  `p9-consumer/install/releases/85546002…/payload/studio`

**(3) HEAD checks.** `run_rehearsal` calls `gt10pc_p9_consumer.run_consumer` in-process
(not `_child`). `prepare_consumer` writes fixture files from
`verify_package(... )["members"]` (`payload/studio/fixtures/gt09-arena/`), not from
the live fixture tree. Install uses the live import `studio.package.ConsumerInstall`
in the matrix process. `native_phase` (`run_gt10pc_native_probe.py`) sets
`PYTHONPATH` to the installed release and calls `run_process` for
`studio.package.installed_probe`, which launches Godot. `support_bundle` writes the
allowlisted bundle. `verify_consumer` (called at the end of `run_consumer`) re-reads
those files, binds ledgers to the archive manifest, checks the support allowlist,
requires the four docs non-empty, and calls `_process` / `_lifecycle` so the host
pid must match the receipt and the stdout must be the lifecycle smoke.
`_verify_rehearsal_matrix` does not call `verify_consumer`.

**(4) Gaps.**

- **MAJOR.** The consumer is not a separate host child. There is no
  `children/p9-*-host.json` and `rows.P9` has no pid. Install runs inside the
  matrix interpreter via the live `studio.package` import, not as a process whose
  only code is the extracted archive. The fixture bytes and the addon tree are
  taken from the archive, and the probe’s `PYTHONPATH` is the installed release,
  so this is not “reads the Windows producer receipt”. Fix: launch
  `gt10pc_p9_consumer` through `_child` (or the same `run_process` helper) and
  require `children/p9-consumer-host.json` plus receipt with `target_pid` and
  `exit_code`. WIP `verify_raw_rows` re-calls `verify_consumer` on the existing
  `p9-consumer/` tree; it does not add that child.
- **MINOR.** HEAD rehearsal verify ignores the Godot host file and the lifecycle
  log. The files are real; the checker that would bind them runs only inside the
  producer. Fix: the same `verify_consumer` call from the verifier (WIP does this).

Not a gap on the smoke itself: Godot 4.7.2 printed a full lifecycle; pid 18804 is
in both `godot-host.json` (written by the `run_process` helper, not by Godot) and
the probe receipt. The support bundle is an allowlist with hashed command ids.
Compatibility lock, runbook, and known limits are in the archive and in the
install tree. One fixture (`gt09-arena`) matches the singular consumer fixture
in P9.

**(5) WIP.** Re-verify of the existing p9 tree is addressed. The in-process launch
and missing `children/` receipt are not.

---

## Cross-row — native steps and who recorded exit/PID

`run_process` (`studio/build/bootstrap/run_fixture.py`, lines 212–285) starts a
helper. The helper writes `{label}-host.json` with `target_pid`, `started_at`,
`exit_code` after `Popen.wait`. The parent adds `wrapper_pid` and
`wrapper_exit_code`. A file in that shape is host-recorded by the parent of the
target. A status string in `matrix.json` is not.

`children/` (matrix parent, schema `hh-gt10pc-matrix-child-1` receipt beside the
host file). All seven exist, exit 0, `tree_verified` true:

| label | host pid | receipt |
| --- | --- | --- |
| windows-producer | 13296 | children/windows-producer-receipt.json |
| p2-native-rejection | 36564 | children/p2-native-rejection-receipt.json |
| p7-native-a | 13772 | children/p7-native-a-receipt.json |
| p7-native-b | 12536 | children/p7-native-b-receipt.json |
| p7-native-c | 12060 | children/p7-native-c-receipt.json |
| p10-installed-gt08a | 41632 | children/p10-installed-gt08a-receipt.json |
| p10-installed-catalog | 33212 | children/p10-installed-catalog-receipt.json |

How the three missing names were launched:

**linux/.** Not a `_child`. `run_rehearsal` calls `gt10pc_linux_producer.run_linux`
in-process (HEAD ~618–626). That function calls `run_process` on `docker.exe` and
writes both the helper host file and a receipt under `linux/host/`:

- image pid 14032, create pid 16212, inspect-created pid 26260,
  run pid 23168 (`docker start --attach <64-hex id>`), inspect-exited pid 27208,
  inspect-closeout pid 20720, remove pid 2888, leftover pid 14588
- each has `linux/host/<label>-host.json` and `<label>-receipt.json`
- `linux/host/run-stdout.txt` is the container stdout captured by that docker
  client (pip install, then `GT10PC_LINUX_NATIVE_COMPLETE`)

`rows.P3`–`P6` only add `"linux": "REHEARSAL_PASS"`. They do not point at
`linux/host/`. Inner Godot/driver files under
`linux/native/consumer/gt09-{arena,room}/{drivers,native}/<phase>/*-host.json`
use container PIDs (12, 24, 34, …, 178). `export_public_evidence` copies them out
of the container. The Windows host did not observe those PIDs. The host-observed
process is docker.exe pid 23168.

**p9-consumer/.** In-process `run_consumer`, as in the P9 section. No `children/`
entry. Godot pid 18804 and driver pid 21480 are wrapper host files under
`p9-consumer/`, recorded by `run_process` from the matrix process. They are not
self-reported by Godot. The consumer Python step itself has no pid.

**p11-short-child/.** This one is a real `_child`, but the directory is
`p11-short-child/`, not `children/`. `p11-short-host.json` pid 40300 exit 0 and
`p11-short-receipt.json` (schema `hh-gt10pc-matrix-child-1`, wrapper_pid 25108)
are host-recorded. Command is `run_native_benchmark.py --run-id gt06-p11-short-318382fd`.
HEAD `_verify_p11_short_row` does not open those two files. It reads
`capture.json` `actual_exits` for import/editor (producer-written capture at the
path in `rows.P11.capture`).

Other nested host files (not matrix children): `windows/drivers` and `windows/godot`
(inside the windows-producer child), `p2-native/driver` and `p2-native/native`,
`p7-native-{a,b,c}/cases/*/native` and `native-driver` (wrapper shape), plus
`p7-native-*/cases/*/worker-host.json` schema `hh-gt10pc-p7-worker-host-1`
(`pid`, `actual_exit`, no `target_pid`), and `p10-catalog/children/*-host.json`
(blender/publication/registered) under the catalog producer. P10’s matrix-level
receipt is the `children/p10-installed-*` pair; the inner files are one level down.

**(4) Gaps.**

- **BLOCKER.** Linux native acceptance in the matrix is the string `REHEARSAL_PASS`.
  HEAD `_verify_rehearsal_matrix` never opens `linux/host/*-host.json` or the
  inspect stdout. Container Godot PIDs are copied self-records from inside the
  container, not Windows host observations. Fix: put the docker `run` receipt on
  the row and make the verifier require `linux/host/run-host.json` (`target_pid`,
  `exit_code`) plus the captured inspect `ExitCode`, and label inner PIDs as
  container-namespace. WIP does not launch linux through `_child`; `verify_raw_rows`
  does call `verify_linux` when P3–P6 are present, which is a re-read of the linux
  tree, but c3e’s matrix row still has no host pid.
- **MAJOR.** P9 and P11 native steps are absent from `children/`. P9 has nested
  wrapper receipts and no consumer pid (see P9). P11 has a real host receipt in
  `p11-short-child/`, and the HEAD P11 verifier does not bind it. Fix: one
  `children/<label>-host.json` plus receipt per native step, and the verifier
  compares that file to the row. For P11, also compare `p11-short-host.json` pid
  40300 to the receipt instead of trusting `capture.json` alone.
- **MINOR.** P7 case `worker-host.json` uses `pid` / `actual_exit` rather than the
  `target_pid` / `exit_code` helper schema. The matrix child for each P7 group is
  still in `children/`. Fix: if those case workers are native steps, record them
  with the same helper. Out of scope for P1/P2/P8/P9 except as inventory.

**(5) WIP.** `verify_raw_rows` re-reads `children/windows-producer-receipt.json`,
P7 children receipts, and P10 children receipts, and calls `verify_linux` /
`verify_consumer`. It does not add a linux or p9 matrix child, and P11 short
verify still does not open `p11-short-host.json`. Launch gaps remain for any
package produced the way c3e was produced.

---

## Gap list (severity)

| row | severity | gap | fix | WIP |
| --- | --- | --- | --- | --- |
| P1 | BLOCKER | Rehearsal verifier accepts P1 from `status` only | Re-open the four hhpkg files in the verifier | partial: `verify_raw_rows` calls `verify_package`; c3e bytes would pass that part |
| P1 | BLOCKER | monetization/failpoint are builder-written manifest flags, not a member-byte scan | Scan archive bytes for payment/voucher/refund/chargeback and an armed failpoint; fail closed | not addressed |
| P1 | MINOR | `reviews/` is not a denylist; c3e has no such member | Reject `zdoc` and `reviews` path segments | not addressed |
| P2 | BLOCKER | Verifier ignores attack bytes, reasons, ledgers, and the children receipt; host loop stores `rejected:true` for any exception | Re-check `p2-attacks`, `p2.json` reasons, before==after ledgers, and `children/p2-native-rejection-host.json` | addressed in `verify_raw_rows` / `_verify_p2_native`; c3e native files support it |
| P2 | MAJOR | known-limits names revoke/expiry/key rotation, not security floor or key-loss recovery | Add those two sentences and rebuild the archive | not addressed |
| P8 | BLOCKER | Subset only (missing godot + package version). No template, no addon mismatch, flags hardcoded, no `p8-host/`. Does not call `gt10pc_p8_checks.py`. GT-08A N03/N04 are canned and are not called | Call `run_p8`/`verify_p8` and keep the five observation dirs | code calls `run_p8`; c3e has no `p8-host/`, so this package still fails |
| P9 | MAJOR | Consumer is in-process; no `children/p9` pid. Smoke Godot pid 18804 is a real nested wrapper receipt | Launch the consumer via `_child` and record host pid/exit | re-verify of existing tree only; launch unchanged |
| P9 | MINOR | HEAD rehearsal verifier does not re-read the Godot host file or lifecycle log | Call `verify_consumer` from the verifier | addressed for the existing `p9-consumer/` tree |
| cross | BLOCKER | Linux row is `REHEARSAL_PASS`; inner Godot PIDs are container copies; docker host receipts in `linux/host/` are not what the rehearsal verifier reads | Verifier must require `linux/host/run-host.json` pid/exit and inspect ExitCode; do not treat container PIDs as the Windows host receipt | `verify_linux` re-read exists; still no matrix child |
| cross | MAJOR | P11 host receipt is in `p11-short-child/` (pid 40300), not `children/`, and `_verify_p11_short_row` reads `capture.json` instead | Bind `p11-short-host.json` and the receipt in the verifier | not addressed |
| cross | MINOR | P7 `worker-host.json` schema differs from the helper host file | Use `target_pid`/`exit_code` if those workers are native steps | not judged beyond inventory |
