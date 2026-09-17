# S75 editor file-indexing diagnostic package

This is a retrospective exact-byte seal of six existing disposable probe arms,
collected on 2026-09-18. It launches no native processes and changes no engine,
production source, plan, or old raw evidence. It is supplemental investigation,
not benchmark acceptance or an independent critic verdict.

| Arm | Scan / waiter | Observed Objects | TreeItems | Native editor exit |
|---|---|---:|---:|---:|
| indexed-01 | full `scan()` / `filesystem_changed` | 71056 → 71132 (+76) | 4497 → 4535 (+38) | 0 |
| ignored-01 | full `scan()` / `filesystem_changed` | 71042 → 71042 | 4491 → 4491 | 0 |
| indexed-02 | `scan_sources()` / `filesystem_changed` | 71061 → 71137 (+76) | 4499 → 4537 (+38) | 0 |
| ignored-02 | `scan_sources()` / `filesystem_changed` | no census | no census | 86 |
| indexed-03 | `scan_sources()` / `sources_changed(bool)` | 71056 → 71132 (+76) | 4497 → 4535 (+38) | 0 |
| ignored-03 | `scan_sources()` / `sources_changed(bool)` | 71039 → 71039 | 4491 → 4491 | 0 |

Every successful arm creates exactly 38 JSON files with the deliberately synthetic
payload `{"diagnostic_only":true}`. In all three indexed arms, the sole tree with
changed metadata/count is the FileSystem dock's main `Tree@6430`: 22 → 60 entries.
Its 38 new resource paths match the 38 actual synthetic files exactly. All 21,482
Node IDs/classes/paths and all 39 RichTextLabel paragraph counts are unchanged
within every successful arm. Cached resources stay 6 and scan generations are 1 → 2.
This is observed correlation under a direct indexing intervention, consistent
with the two-Object TreeItem/cell mechanism discussed in the sibling review.

`ignored-02` remains failed. Its v2 harness awaited `filesystem_changed` after
an ignored/no-change `scan_sources()` call, timing out before the first census
and before the synthetic files were written. The real native exit record is 86;
`failure.json` reports `BENCHMARK_WRAPPER_EXIT`, stdout reports
`DIAGNOSTIC_SCAN_TIMEOUT`, and cleanup records Job zero/closed and a released
wrapper handle. It has no `editor-host/capture.json`, result, or census, and none
has been manufactured. Its earlier one-cycle COMPLETE/index marker does not
make the subsequent diagnostic successful. V3 changes the waiter to
`sources_changed(bool)` and both fresh arms complete.

All six imports exit 0. The five successful editor arms have actual exit 0 and
hash-bound capture artifacts. Each terminal editor owner record shows Job zero,
closed, and released wrapper handles. Indexed-03's import capture records
`active_at_wrapper_exit=1`, then `active_before_cleanup=0` and final Job zero/closed;
the package preserves those distinct observations without flattening them.
Cleanup is not an in-run kernel-handle or RSS measurement.

## Provenance and contents

The raw roots remain under `studio/.local/reviews/gt06-s75-editor-files-*`.
`raw-inventory.json` hashes every raw file, including cache files not copied here.
`copy-map.json` binds selected exact copies to their original relative paths.
The selection includes all census data, frozen base source, non-cache project
files (including generated native scripts and synthetic payloads), source maps,
results/failure, and direct owner logs, invocations, process records, captures,
and cleanup records. Cache/user-profile trees remain raw-only and inventoried.

The three scripts in `scripts/` are preserved exact harness versions; their
hashes must equal each original `diagnostic.json.runner_sha256`. They are copied
for inspection, not to be executed from this relocated directory. V1's 38-file
base map omits the runtime non-Python dependency
`contracts/perf-collector.schema.json`. V2/v3 bind it in 39-file base maps.
The package verifies every declared base and runtime hash against each arm's
frozen snapshots. It does not assign changed live production bytes to old probes
or claim that verifying declared v1 files fixes its incomplete provenance.
Initial immutable project hashes are checked; the declared mutable fixture
scene is retained and its initial/final equality is reported separately.

`summary.json` contains independently recomputed counts, source closures, path
deltas, harness bindings, and process outcomes. `MANIFEST.json` binds every
package payload, including this README and collector. The hash domain is SHA256
over sorted UTF-8 `path + NUL + sha256(exact bytes) + LF`; the manifest excludes
itself and its exact-byte SHA256 is printed by verification.

## Limits and verification

These short probes perform one semantic cycle and synthetic file creation with
an explicit scan intervention. They do not exercise the complete normal
ready/start/joint/ACK workload, 100-cycle batches, 35-batch runs, or 10-process
campaign. They do not prove that the original failed campaign's extra 38 Objects
were 19 newly indexed files, explain its extra two kernel handles, or resolve RSS
failures. Census data is primitive Node/TreeItem column0/RichText information,
not a complete ObjectDB class inventory. This seal binds the presently retained
census bytes; it is not a retroactively invented native census-hash receipt.
The original campaign remains failed and all acceptance thresholds stay intact.

From the repository root, run the following read-only verification. It checks
the seal, every original raw hash and exact copy, frozen source maps, process
artifacts, census identities/paths/paragraphs, and all six outcomes. It imports
no project implementation and starts no native executable.

```powershell
python -X utf8 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s75-recovery/editor-files-proof/collect.py
```

`--collect` rebuilds this package from existing raw only; it must not be used to
relabel future changed raw as the same historical seal. No commit was made by
this evidence-collection worker.
