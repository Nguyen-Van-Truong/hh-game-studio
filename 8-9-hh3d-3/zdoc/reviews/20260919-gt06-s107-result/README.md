# S107 result — preview cost observed, S102 cause unresolved

AUTHORITY=0. Diagnostic, not F13/F14, formal PASS, leak proof or final critic.

`gt06-s107-preview-01` ran 2026-09-19T06:08:11Z–06:08:41Z under the unchanged
S102 base53/profile and the separately frozen S107 diagnostic recipe. It
completed all 40 native cycles, ten ABBA groups, with no HTTP/PSS. All original
heartbeat/phase limits were retained. No extra warmup or outlier was discarded.

| Call duration | A: stock save with preview | B: save without preview |
|---|---:|---:|
| Mean | 108.95045 ms | 30.4063 ms |
| Median | 106.576 ms | 29.7685 ms |
| p95, nearest rank | 123.049 ms | 34.116 ms |
| Maximum | 138.095 ms | 38.803 ms |

Every group has positive A-minus-B mean call time: 70.8865–94.8215 ms.
All observations and paired differences are retained in `analysis.json`.
This supports a preview-path cost in this fixed short experiment. It does
not reproduce the 2109.351 ms S102 heartbeat gap, explain batch6 residency,
prove a production-publication optimization, or authorize a formal workload
change. The stock benchmark save coverage remains unchanged. No repeat of
this 40-cycle contrast is needed.

Call return and signal are separate; first-A serialization normalization is
retained. All 40 saved/reloaded scene hashes match after normalization; script
bytes, semantic undo/reload, generation and root transitions were validated.
The portable reader recomputes its interpretation from exact stdout/report/
index artifacts. Collector also bound each row to native batch semantics and
timings before returning `CAPTURED`.

Actual target exits: editor4768=0, import35964=0, child33532=0; each helper=0.
Passive outer observer retained runner49464 and recorded actual exit0.
Jobs reached zero and closed; editor/host wrapper handles and probe/import
observer releases were recorded. Import-wrapper native handle close remains
UNKNOWN in the reused API; managed Process.Dispose is not native CloseHandle
BOOL. No live Stop test was performed. These gaps are preserved, not promoted
to acceptance.

`raw/`, `outer/`, `frozen/` and `observer/` are exact selected copies. Original
and portable path domains have separate closure hashes. Cache, temp and
localappdata were excluded; selected UTF-8 files received a bounded secret
pattern/key screen. The packet reader needs no original raw directory or
engine imports. The manifest excludes itself and the subsequent verification
receipt to avoid circular hashes.

```powershell
python -B zdoc/reviews/20260919-gt06-s107-result/verify_packet.py
```

Source/helper preparation checkpoint: `f95fb8cc`. No runtime source, profile,
threshold, working-set policy, process priority or unrelated application was
changed. GT06 remains IN_PROGRESS with zero accepted complete benchmark runs.
