# S79 service remint dependency plan

AUTHORITY=0. Read-only preparation at `24efe96757a7b0a25c4a11471152fd1911d764f0`, 2026-09-18 approximately 06:28 UTC / 13:28 Asia/Saigon. No runtime edits, tests, engine launches, raw-tree hash audit, gate change, or acceptance claim. The coordinator reports the S79 owned index lane passed 95/95; that does not replace native service evidence.

**Remint the five S73 native service lanes on the new service/index source.** Managed replay remains reusable on its separately verified dependencies. Existing reviewer UI observations remain reusable only as UI-specific historical evidence: the complete S68 GUI runs are not exact-current full-stack runs because they instantiate the changed service. If current integrated GUI behavior is part of the final claim, refresh the two GUI lanes too.

## Exact dependency result

Inputs:

- `zdoc/reviews/20260918-gt06-s75-recovery/next/affected-dependency-bridge.json` and `README.md`.
- `zdoc/reviews/20260918-gt06-s73-next/seal/affected-dependency-bridge.json`.
- `zdoc/reviews/20260918-gt06-s73-recovery/service-remint/verification.json`, per-lane invocation/capture records, and raw runtime source maps.
- Current `run_service_probe.py`, `run_service_adversary.py`, `backend.py`, `native_runner.py`, reviewer runner/main, and campaign source collector.

I compared the declared source bytes for five S73 service maps, one S69 managed replay map, two S68 GUI runtime maps, and two S68 UI maps. The union contains **178 source files, 1,922,520 bytes**; all existed. Each source was hashed once, within a 3 MB cap. No raw screenshots, GLBs, executables, journal histories, campaign trees, or large evidence packages were hashed.

| Lane/domain | Current projection | Disposition |
| --- | --- | --- |
| S73 HTTP complete, HTTP Stop, saturated Stop, revoked result, stale capture | In each historical 173-file map, exactly `host/replay/service.py` and `host/replay/verified_journal.py` changed; no declared path missing. Current backend dependency enumeration also adds `host/replay/disk_journal_index.py`. | All five native service lanes need new run IDs/current source maps. Expected backend source count is now 174 if no further dependencies change. |
| S69 `gt06-s69-managed-replay-01` | All 159 declared files match. Its four `repair-replay.json#/verifier_sources` values also match current source: repair, repair_replay, observation, trace. No service, VerifiedJournal, or disk index dependency. | Reuse the original scoped native repair/replay, retaining S65 repair02 provenance. Do not repeat the accepted repair mutation for these changes. |
| S68 reviewer complete/Stop UI | Both five-file maps match, including `reviewer/main.py` and `tests/reviewer/run_reviewer_probe.py`. | Reuse UI-only layout/key/button/visible-observation evidence under its original IDs. This does not prove new failure behavior or current end-to-end service integration. |
| S68 reviewer complete/Stop full runtime | Both 173-file maps differ at service and VerifiedJournal; current backend also adds disk index. `reviewer/main.py` directly constructs ReplayService. | Do not label either full GUI run exact-current. Refresh complete/Stop if the final package claims current integrated GUI behavior. A five-lane service bridge may supplement historical UI observations, but is not a new GUI execution. |
| S78 benchmark campaign | `campaign.json#/source_files` includes disk index and VerifiedJournal, but not ReplayService. The command producer constructs VerifiedJournal and `LoopbackFixtureHost`. | The disk-index edit invalidates current campaign-source equality. The ReplayService edit alone does not. S78 was terminal FAILED regardless; no samples may become a new run's PASS. |
| Standalone native/editor/owner diagnostics and GT03–05 histories | This task did not compare each separate dependency domain. | Keep original provenance; claim reuse only through its own unchanged dependency map. No blanket inference from service tests or UI equality. |

Why both changes affect all five service lanes: each driver imports ReplayService; `service.py` imports VerifiedJournal; VerifiedJournal imports DiskJournalIndex. `PreparedPlay.prepare()` (`backend.py:51–59`) starts with `native.sources()` and adds every `host/replay/*.py`. Thus the new index must be included even though it did not exist in the old 173-file maps. A historical-map-only comparison that omits added paths is incomplete.

The earlier S75 reuse decision was valid only for its benchmark-only changes. It explicitly found the five S73 service runtime maps unchanged then. It is not a standing permission to reuse them after S78/S79 journal/service changes. The old broad 148-file service review-runner map is a separate domain; neither it nor the campaign49 closure is the current service174 map.

Changed/source identities:

| Path under `studio/` | Recorded S73 | Current |
| --- | --- | --- |
| `host/replay/service.py` | `a09641c7954938aebf1207bd37bf66825eb483e51e7c386032b09fcde496121a` | `d8d046ea2144ade026cce7e63a53b52885a28b213193fed19f932a773a9758a5` |
| `host/replay/verified_journal.py` | `9128749e6a04242106e56a86e959b6de0a67e0f10ffb97965e1bc88390d5a6f2` | `129baa4d9e08c8a1d5acf2ea05c9c89a4fdddb53ca6f3baf2d61311ab98e62ab` |
| `host/replay/disk_journal_index.py` | absent | `56beb93119dfb66feec32eb51d389fc089d89911c0a1be199071c17e1801cb28` |

The two current service drivers themselves are unchanged from S73: probe SHA-256 `436c965f06beef99ec2b3c10817aa9e098063ad9cf80db48d1fdc40f62a53d32`; adversary `e094de0d7e89f68b35f22f9afcf300d14864733f9c5cad5ef42a63b394b5fed2`. S68's old VerifiedJournal value was `3bdc1414166c132236149629b14bde456d142578cc3d08e0fd1faf5a4285d5eb`, which is also not current.

## Five required service runs and prior duration evidence

Use fresh IDs below; all their base, `-outer`, and `-driver` raw roots were absent when checked. Recheck absence immediately before dispatch. Serialize them after the current native diagnostic reaches terminal and its owner is released. Do not overlap with a benchmark measurement.

| Suggested run ID | Entry/mode | S73 import + native runtime elapsed | Planning estimate, including wrapper/HTTP overhead |
| --- | --- | --- | --- |
| `gt06-s79-http-complete-01` | `run_service_probe.py --mode complete` | 5.172 + 7.938 = **13.110 s** | about 25–35 s |
| `gt06-s79-http-stop-01` | `run_service_probe.py --mode stop` | 5.172 + 0.250 = **5.422 s** | about 8–15 s |
| `gt06-s79-saturated-stop-01` | `run_service_adversary.py --mode saturated-stop` | 4.937 + 0.203 = **5.140 s** | about 8–15 s |
| `gt06-s79-revoked-result-01` | `run_service_adversary.py --mode revoked-result` | 5.047 + 7.703 = **12.750 s** | about 22–35 s |
| `gt06-s79-stale-capture-01` | `run_service_adversary.py --mode stale-capture` | 5.015 + 7.735 = **12.750 s** | about 22–35 s |

Elapsed values above are read from each raw `import-host/capture.json` and `runtime-host/capture.json`. They are not total lane wall time. Adjacent S73 coordinator target-start intervals were approximately 27.460, 8.143, 8.722, and 22.141 seconds; those include inter-run overhead and are not exact completion durations. The last lane has no successor-start duration in these records. Budget roughly **2–3 minutes** for five successful serial runs plus collection; timeouts remain guards, not estimates or loosened acceptance limits.

S73 recorded 96/12/15/18/17 checks (158 total). Some complete-lane checks are repeated lookup polls, so do not force the new run to the old numeric total. Require each named invariant and every emitted check to pass.

The existing adversary parent owns a 150-second child bound and writes `<run>-outer/capture.json`. `run_service_probe.py` has no equivalent outer wrapper; it must receive coordinator-owned process capture. The old S73 coordinator wrapped all five runners. Retain that model: for example 150 seconds for each probe outer target and 180 seconds for each adversary outer target, keeping the adversary's existing inner150 limit unchanged. Normal replay requests still use their existing lease/deadline and 27-second terminal-observation bounds.

## Runnable payloads and owned dispatch

Working directory is the repository's `8-9-hh3d-3` folder. Use the pinned Python from the prior lane, `C:/Users/truon/AppData/Local/Programs/Python/Python311/python.exe`, with `-B`. These are the exact payload arguments for the coordinator's frozen owned launcher, not acceptance evidence when launched bare:

```powershell
python -B studio/tests/replay/run_service_probe.py --run-id gt06-s79-http-complete-01 --mode complete
python -B studio/tests/replay/run_service_probe.py --run-id gt06-s79-http-stop-01 --mode stop
python -B studio/tests/replay/run_service_adversary.py --run-id gt06-s79-saturated-stop-01 --mode saturated-stop
python -B studio/tests/replay/run_service_adversary.py --run-id gt06-s79-revoked-result-01 --mode revoked-result
python -B studio/tests/replay/run_service_adversary.py --run-id gt06-s79-stale-capture-01 --mode stale-capture
```

Do not pass `--child` to the adversary entry point; its public entry supplies the owned inner capture. A coordinator launcher can use the existing proven API below once its own invocation/source inventory is frozen. This is an executable dispatch skeleton, not a final validator; the result requirements in the next section still apply.

```python
from pathlib import Path
import importlib.util
import json
import sys

root = Path.cwd().resolve()  # 8-9-hh3d-3
studio = root / 'studio'
runner = studio / 'build/bootstrap/run_fixture.py'
spec = importlib.util.spec_from_file_location('s79_service_owned', runner)
owned = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owned)
base = root / 'zdoc/reviews/20260918-gt06-s79-diagnosis/service-remint-01'
base.mkdir(exist_ok=False)
lanes = [
    ('http-complete', 'run_service_probe.py', 'complete', 150),
    ('http-stop', 'run_service_probe.py', 'stop', 150),
    ('saturated-stop', 'run_service_adversary.py', 'saturated-stop', 180),
    ('revoked-result', 'run_service_adversary.py', 'revoked-result', 180),
    ('stale-capture', 'run_service_adversary.py', 'stale-capture', 180),
]
for label, driver, mode, timeout in lanes:
    run_id = 'gt06-s79-' + label + '-01'
    for suffix in ('', '-outer', '-driver'):
        assert not (studio / '.local/reviews' / (run_id + suffix)).exists()
    output = base / label
    output.mkdir(exist_ok=False)
    argv = [sys.executable, '-B', str(studio / 'tests/replay' / driver),
            '--run-id', run_id, '--mode', mode]
    (output / 'invocation.json').write_text(json.dumps({
        'argv': argv, 'run_id': run_id, 'mode': mode,
        'timeout_seconds': timeout, 'formal_acceptance': False}, indent=2) + '\n')
    host = owned.run_process(argv, cwd=root, output=output,
                             timeout=timeout, label='owner')
    (output / 'capture.json').write_text(json.dumps({'host': host}, indent=2) + '\n')
    if not (host['exit_code'] == host['wrapper_exit_code'] == 0
            and host['tree_verified'] and not host['timed_out']):
        raise SystemExit('Retain failed lane and reconcile ownership before another launch')
```

Before using that skeleton, add the coordinator's normal frozen source snapshot and before/after equality checks, including added dependencies and the launcher itself. The current owned index launcher in this same directory demonstrates that source-capture pattern, but its fixed test invocation is not a service launcher and must not be reused unchanged. Preserve immutable source copies and actual `owner-host.json`, not only the wrapper's summarized exit. The skeleton has not been executed by this reviewer.

## Evidence required for the remints

For each lane retain the new backend `source-files.json`, source copies, invocation, native import/runtime invocation and logs, actual process exits, Job zero/close state, and the matching `http-probe/result.json` or `http-adversary/result.json`. Include the driver hash, wrapper source/argv, before/after source equality, command/lease/request/source bindings, and all recorded HTTP checks. For adversaries also include the distinct `<run>-outer` process/capture/logs.

- Complete, revoked result, and stale capture require actual native exit0 tied to native identity and a closed/zero, untainted Job. Both outer levels must finish successfully where present.
- Stop and saturated Stop intentionally have `completed=false` runtime captures. Preserve a missing natural native exit as missing; require the recorded stopped/zero/closed Job, no retained handles, and actual successful outer exits. Never manufacture native exit0 from wrapper0.
- Complete must prove native terminal readback, same-ID dedupe, historical inspection/capture, and clean owner close.
- Saturated Stop must retain its real held sockets/work-slot observations and priority lookup/Stop timings; a fake busy flag is not equivalent.
- Revoked result must remain UNKNOWN with no public ACK and no replay authority. Stale capture must retain its original-copy/hash/mutation witness and rejection; do not normalize the intentionally changed PNG as a success artifact.
- Retain the new 95/95 owned fault lane separately. These normal native runners do not inject SQLite close/commit or watchdog-start failures; they supplement rather than replace the new unit fault cases.

## GUI refresh boundary and commands

The S75 bridge allowed historical UI observations plus a current service bridge for its narrowly changed journal dependency. Preserve that claim boundary explicitly. Matching five UI files does **not** mean their transitive service dependency matches. If final claims include current reviewer→service→native complete/Stop behavior, use fresh GUI runs:

```powershell
python -B studio/tests/reviewer/run_reviewer_probe.py --run-id gt06-s79-reviewer-complete-01 --mode complete
python -B studio/tests/reviewer/run_reviewer_probe.py --run-id gt06-s79-reviewer-stop-01 --mode stop
```

The public reviewer entry already owns its child with a110-second bound; retain its `-driver` capture and any coordinator outer capture. Prior S68 import+native elapsed was 8.187+8.422=16.609 seconds for complete and5.235+0.250=5.485 seconds for Stop. The historical complete→Stop driver-start interval was53.441 seconds, so budget about45–65 seconds for complete and10–20 seconds for Stop, subject to actual machine state. Keep real UI window/keyboard evidence; a service-only run cannot stand in for it.

S69 managed replay's exact159-file equality and matching verifier hashes justify preserving its existing native results and original fault→repair→replay causal links. No remint of that lane is caused by service/index changes. All reuse remains scoped to those recorded dependencies and claims, not a transferred source hash, signature, or full GT06 acceptance.
