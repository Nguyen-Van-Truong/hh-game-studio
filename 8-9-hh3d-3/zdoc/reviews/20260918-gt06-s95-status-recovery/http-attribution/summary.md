# S95 HTTP attribution run-01

The supplemental run completed 20 ten-command HTTP groups: 100 inspections,
60 expected rejections, 40 admissions and 40 mock effects, plus 20 cancellation
probes. All 160 lookup attempts ended COMMITTED or CANCELED; UNKNOWN receipts,
UNKNOWN terminals and non-null transport failures were all zero. This is
diagnostic evidence, not formal acceptance or a demonstrated fix for S93.

The source hashes differ because their file sets differ. The HTTP freeze
`1d7726ca9af7c05989aa5bcd4b74372ab386af41c0ca8d7d43381df1752ad7b7` has 48 files.
The formal source map at commit `ad81e9444313e6d5cf5bc084d5f771582f16c60c`, closure
`564e5b7877f49d33a1af84eaf3b3a7ddf4ea2f846c4161eb694c5c40514fc752`, has 51 files.
All 48 shared path/hash pairs match exactly; HTTP has no extra path. The three
formal-only paths are `godot-addon/bundle_staging.py`, `godot-addon/bundle_v2.py`
and `godot-addon/fixture_profile.py`. The collector includes imported modules;
this HTTP launcher does not load the dynamic Godot fixture factory. The narrower
closure does not replace the formal one. Exact additional hashes are in
`analysis.json`, derived from `run-01/freeze.json` and `../source-current.json`.

Current source and its snapshot stayed unchanged. Only the history came from
S93: 6,928,143 bytes, SHA-256
`1e12bfae2d5fe2da1947447a6b75c3da073811baefc70fc6f095513ebc1d361f`.
Both original and copied input history remained unchanged.

Initialization's journal load took 5,031.4 ms, before HTTP timing started.
The 20 HTTP groups covered 20,551.829 ms. Their largest reported progress gap
was 401.4742 ms, in group 11. The target did not reach its 105-second deadline.

| Instrumented operation | Calls | Largest span, ms |
|---|---:|---:|
| Journal snapshot | 782 | 53.4395 |
| Journal reload | 780 | 53.4820 |
| Journal append | 340 | 336.0078 |
| Writer wait | 781 | 29.6578 |
| Writer held during HTTP | — | 353.2521 |
| Host command dispatch | 220 | 399.1932 |
| Host lookup dispatch | 160 | 139.7425 |

The largest HTTP dispatch belongs to group 11, inspection ordinal 4. Its
399.1932 ms span contains a 353.2521 ms writer-held span and a 336.0078 ms append
span; raw inspection time through terminal readback was 455.2747 ms. These are
nested observations, not additive timings. They locate time within this sampled
dispatch but do not distinguish append encoding, SQLite, file IO, fsync or
scheduling, and do not explain S93's rare lookup latency. Maximum raw lookup
interval was 141.931 ms. No UNKNOWN or two-second gap was reproduced.

Actual target 8824 and helper 13900 both exited 0, with owned Job tree zero and
no timeout. The producer closed; three threads stopped, both sockets closed,
journal cache/index closed, and observer handle released without uncertainty.
Both captured logs were empty. This runner lacks the S93 observer's additional
retained process-handle close receipts; its narrower cleanup proof stays labelled.

Only the largest sixteen spans >=50 ms per operation were retained. Aggregate
totals mix phases, wrappers add overhead, and a non-returned wrapper is not a
protocol failure counter. This short HTTP-only workload did not run an engine,
reproduce the original 1000-command/native sequence, establish a root cause,
prove ObjectDB behavior or produce an F13/F14 acceptance verdict.
