# S224 — derived correction for the sealed S218 RSS failure

Authority is `0`. This packet corrects derived reporting only; it does not alter the sealed raw package, gate, profile, baseline, timeout, or acceptance status.

The selected raw files match the S218 manifest byte-for-byte. Replaying the historical `screen_sample` from commit `5a054cc3` and the current additive implementation both return `CAMPAIGN_RSS_GROWTH` for batch 5. The first failed row is the host RSS row: 27,451,392 → 38,883,328, above the frozen 110% limit of 30,196,531. The editor RSS row also fails independently: 105,934,848 → 161,259,520. The assembled sample status gap is 1,675.9498 ms; the native barrier receipt reports 691.731 ms.

`host-owner/process-exit.json` binds PID 23980 to actual exit code 1, and `host-owner/cleanup-001.json` proves its Job/owner cleanup. The editor target still has no actual-exit receipt, so it remains `UNKNOWN`; no exit is inferred from scheduler state or process absence.

The implementation adds a failure-only `screen_observation` to new receipts and tests the simultaneous-failure ordering. It does not rerun the engine and does not make this a formal continuation. The current source closure is computed only after `load_fixture()` and contains 53 files. A fresh formal campaign remains unjustified until a distinct supported RSS measurement boundary or owner ADR exists.

The sealed phase window records its first lookup transport failure in batch 1. The batch 4 and batch 5 host command RSS samples are 37,642,240 and 37,224,448 bytes, respectively; this does not establish a host allocation root cause for the later joint RSS row. `verify.py` checks 21 selected raw files against the sealed manifest, replays both screen predicates without mutating the samples, and confirms the current 53-file closure. The campaign, assembly, and profile tests run 34/35/19 successfully (88 total). The three requested Astra xhigh workers were capacity-rejected before contributing; no model fallback was used.
