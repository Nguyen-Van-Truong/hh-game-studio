# S111 static attribution sidecar

This sidecar is derived from the immutable S110 failure packet. It does not alter or replace S110 raw evidence and is excluded from GT06 acceptance/F13/F14.

- Source closure: `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`
- Probe: `journal-reload-probe.json` copies S110 `commands.jsonl` into a private temporary file and measures the existing `Journal` loader only. It is offline; no Godot engine, HTTP server, or benchmark campaign ran.
- Result: 5,797,257 bytes / 8,292 lines; five reloads 2.764–3.117 s (median 2.831 s); five lookup calls 2.856–2.982 s (median 2.902 s). Lookup returns `RETRY_HORIZON_EXPIRED` after timing, which is expected for the preserved historical timestamp and does not invalidate the timing.
- Interpretation: the preserved journal snapshot/reload path can exceed the unchanged 2 s transport boundary on this workstation. This supports a narrow command-lane attribution hypothesis; it does not prove all S110 latency, engine causation, a memory leak, or a repair.
- Static verification: journal-index 14/14, disk-journal-index 5/5, transport 13/13; all exit 0. No formal retry is authorized by this sidecar.
