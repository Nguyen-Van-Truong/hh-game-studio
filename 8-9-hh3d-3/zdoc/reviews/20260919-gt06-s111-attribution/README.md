# S111 static attribution sidecar

This sidecar is derived from the immutable S110 failure packet. It does not alter or replace S110 raw evidence and is excluded from GT06 acceptance/F13/F14.

- Source closure: `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`
- Probe: `journal-reload-probe.json` copies S110 `commands.jsonl` into a private temporary file and measures the existing `Journal` loader only. It is offline; no Godot engine, HTTP server, or benchmark campaign ran.
- Result: 5,797,257 bytes / 8,292 lines; five reloads 2.764–3.117 s (median 2.831 s); five lookup calls 2.856–2.982 s (median 2.902 s). Lookup returns `RETRY_HORIZON_EXPIRED` after timing, which is expected for the preserved historical timestamp and does not invalidate the timing.
- Interpretation corrected by S112: the base `Journal` reparses history and can exceed 2 s here. The running service uses `VerifiedJournal`, so these timings do not attribute the S110 live snapshot delay. Keep the original probe as historical evidence; no repair follows from it.
- Static verification: journal-index 14/14, disk-journal-index 5/5, transport 13/13; all exit 0. No formal retry is authorized by this sidecar.

## Exact live-path probe

`verified-journal-probe.json` instantiates the exact `VerifiedJournal` used by `ReplayService` on a fresh copy of the S110 journal. Initialization (full validation/index build) took 4364.311 ms, but unchanged verified snapshots took 12.136–19.592 ms (median 16.499 ms), reloads 10.971–16.185 ms (median 14.351 ms), and lookups 16.109–21.359 ms (median 17.021 ms). Historical lookup returns `RETRY_HORIZON_EXPIRED` after timing, as expected. This means the static base `Journal` result must not be applied to the live service: the existing cache/index path is fast on an unchanged copy. It does not prove S110 was impossible or establish a fix; runtime contention/phase attribution remains unresolved.

The extended static set totals 68 cases, all exit 0: the original journal/index/transport tests plus VerifiedJournal (11), index faults (12), protocol journal (8), and journal CAS (5). No engine or campaign ran.

The probe scripts were temporary local scripts, not frozen execution closures. These files preserve derived measurements only. They are not formal acceptance or a substitute for the owned, seeded HTTP replay prepared in S114.
