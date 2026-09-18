# S79 current-source service and reviewer remints

AUTHORITY=0. No gate acceptance, critic signature, plan tick, runtime edit, or commit.

Seven serialized lanes completed on source checkpoint `24efe96757a7b0a25c4a11471152fd1911d764f0`.
Frozen Git HEAD was `e4bbc1fe3a99d5860fb0c5ca9e163860b05f4d2a` (evidence-only follow-up),
as recorded in `freeze.json`; source binding uses exact per-file hashes. Runs:
2026-09-18 06:44:41–06:47 UTC. The launcher and rechecker both returned actual
shell exit 0. Each lane independently retains its owned helper exit and actual
target exit in `capture.json` and `owner-host.json`; adversaries and GUI lanes
also retain their distinct inner owned captures. No old run ID was reused.

| Fresh run ID | Outcome | Runtime PID | Actual natural exit |
| --- | --- | --- | --- |
| gt06-s79-http-complete-01 | 89 HTTP checks passed | 45000 | 0 |
| gt06-s79-http-stop-01 | 12 HTTP checks passed | 35872 | missing, preserved as null |
| gt06-s79-saturated-stop-01 | 15 HTTP checks passed | 23944 | missing, preserved as null |
| gt06-s79-revoked-result-01 | 18 HTTP checks passed | 51768 | 0 |
| gt06-s79-stale-capture-01 | 17 HTTP checks passed | 36900 | 0 |
| gt06-s79-reviewer-complete-01 | Play key, inspector/capture buttons, clean close | 23748 | 0 |
| gt06-s79-reviewer-stop-01 | Play/Stop keys, stop latch, clean close | 51760 | missing, preserved as null |

The 151 service checks include every named S73 invariant. Complete's lookup poll
count varies, so the historic total 158 was not enforced. Existing time bounds,
drivers, acceptance conditions and native owners were unchanged. Seven imports
captured native exit 0. All fourteen import/runtime Jobs were empty, closed,
untainted, and retained no Job handle. The three Stop runtimes retain
`completed=false`, `STAGE_STOPPED`, and wrapper exit 2; successful outer exits
are not substituted for missing natural native exits. Every owned outer/inner
target and helper exited 0 and recorded an empty owned process tree.

Saturated Stop occupied both work slots using two real incomplete sockets;
priority lookup took 9.1427 ms and Stop 3.8098 ms while work remained saturated.
Revoked result stayed UNKNOWN without public ACK or replay authority. The stale
capture's original PNG, XOR mutation witness and rejection are retained. The
generated modified PNG is intentionally unchanged after the test.

Reviewer Complete and Stop exercised the existing Tk keyboard/button runner
against the current service. Heartbeat maxima were respectively 437 ms and
32 ms; these are observations, not a full UX/performance benchmark verdict.

`freeze.json` includes 453 source/helper/driver/launcher files and immutable
copies. Each backend map contains the exact current 174 files, including the
new disk index, with closure:

`644b90abfe769bf1a3654ba506cef50f8a38393f05f0be5ca7aae8050aaaa527`

Launcher SHA-256:
`2882623fdf73370456763b0e27e52c7783bd92fb1fd83086cb07a9ad42fe252a`.
Freeze SHA-256:
`adea95e23a6487f879e5e41a366530286869c0ccca05bcbd49fad68af5b70f28`.
The post-run `recheck.json` verifies all frozen live/copy bytes, native process
records, 1,778 raw files (60,882,574 bytes), and 1,663 selected exact copies.
Generated engine caches remain only in their original raw roots; selected
copies preserve sources, requests, results, logs, process records and artifacts.
Per-lane `raw-files.json` preserves the complete raw hash inventory.

`leftover-check.json` records no Godot/Blender or S79 lane Python processes at
06:47:27 UTC. The engine lease was released to the coordinator after that query.
`git diff --name-only -- studio` was empty after the runs. Only this remint's
launcher and review artifacts were authored by the worker; generated raw trees
were written by the unchanged drivers to their usual fresh `.local/reviews` IDs.

Read-only reproduction from `8-9-hh3d-3`:

```powershell
& 'C:/Users/truon/AppData/Local/Programs/Python/Python311/python.exe' -B 'zdoc/reviews/20260918-gt06-s79-diagnosis/service-remint-01/verify.py'
```

The executable launch recipe is preserved in `../run_service_remints.py`,
alongside per-lane argv/cwd/timeout records. It rejects existing run roots;
rerunning it against these IDs is intentionally forbidden. This remint
supplements the separate 95/95 index-fault lane and does not replace the full
GT06 campaign, managed replay provenance, or two independent final critics.
