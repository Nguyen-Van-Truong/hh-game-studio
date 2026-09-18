# S81 dependency impact — read-only check

AUTHORITY=0. Status: **accepted dependency bytes restored; exact joins pass**.
Read-only verification at 2026-09-18 08:06:01-08:06:47 UTC. No native run, test,
runtime edit, remint launcher or remint output was created by this investigation.
This preserves the scoped historical source identities; it is not a new source
freeze or an acceptance verdict for the benchmark changes.

## Exact file joins before isolation

I parsed the original raw manifests and hashed the union of 179 declared
current files once. No declared file was missing. For every row below, the
complete map was joined by path and SHA-256, not just by a remembered closure.

| Original lane | Domain | Exact comparison before isolation |
|---|---:|---|
| `gt06-s79-http-complete-01` | backend 174 | 173 match; only `host/core/transport.py` differs |
| `gt06-s79-http-stop-01` | backend 174 | 173 match; only `host/core/transport.py` differs |
| `gt06-s79-saturated-stop-01` | backend 174 | 173 match; only `host/core/transport.py` differs |
| `gt06-s79-revoked-result-01` | backend 174 | 173 match; only `host/core/transport.py` differs |
| `gt06-s79-stale-capture-01` | backend 174 | 173 match; only `host/core/transport.py` differs |
| `gt06-s79-reviewer-complete-01` | backend 174 + UI 5 | backend has the same one-file difference; UI 5/5 match |
| `gt06-s79-reviewer-stop-01` | backend 174 + UI 5 | backend has the same one-file difference; UI 5/5 match |
| `gt06-s69-managed-replay-01` | runtime 159 | 158 match; only `host/core/transport.py` differs |

Each backend map is `studio/.local/reviews/<run-id>/source-files.json`; the two
UI maps are `reviewer-probe/source.json` under their respective raw roots.
Original manifest file SHA-256 values:

- Seven identical S79 backend maps:
  `63f6f5a9058a6f62e9db39e9eec362f79c88aa4b5510710dbcdf53ced5ab2208`.
- Two identical S79 UI maps:
  `4476fe477abab0859f9957403d84ab3a869db458f46b4ff251672ffc560df640`.
- S69 managed runtime map:
  `b0091dc3e16801af4c8bb39f39da9bb4bfd8b71be66f0ade7dac1e9b522ed11c`.

The changed paths were joined explicitly against every map:

| Path under studio | S79 backend 174 | S79 UI 5 | S69 runtime 159 |
|---|---|---|---|
| `host/core/transport.py` | present, changed | absent | present, changed |
| `tests/replay/benchmark_commands.py` | absent | absent | absent |
| `tests/replay/run_benchmark_campaign.py` | absent | absent | absent |

The common recorded transport SHA-256 is
`1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0`.
The working transport at the mismatch observation was
`98f154f042981306db257ce3f2aa40cedc3188166a5f6c32f88d07adcb1d4fa5`.
The two working benchmark files then hashed respectively
`e14d4794649e6341f3a7b10a6c7cbd1bcfb1369eb2a3d06e2b7a86453aefe21a`
and `e6f2570f4eeeed7c0263b8d3f6596e4486cb8c63afe21477f4d91e8481f63d4c`;
the cleanup worker was still editing, so those are observations, not frozen
candidate identities. No new `host/replay/*.py` was absent from the S79 map.

S69's four separately recorded verifier files also all matched:
`repair.py`, `repair_replay.py`, `observation.py`, and `trace.py`. Their hashes
remain those in original `repair-replay.json#/verifier_sources`. Preserve that
managed replay's S65 repair02 causal anchor and original evidence identifiers.

## Why native remint was held

`native_runner.sources()` rehashes each accepted GT05 manifest source before
preparing a replay. The immutable accepted manifest
`zdoc/reviews/20260917-gt05-s63-audit/manifest.json` has SHA-256
`fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b`
and pins `8-9-hh3d-3/studio/host/core/transport.py` to `1ec03356...` above.
The observed edit would therefore raise `REPLAY_REUSE_SOURCE_CHANGED` before
native launch. The historical S79 remint launcher calls this check directly.
Changing run IDs cannot resolve this source dependency; changing the accepted
manifest or bypassing its check would alter the gate.

The narrower static check explains the proposed isolation, but is **not** an
exact-file equivalence claim. The only modified existing top-level transport
definitions were `FixtureFaults`, `LoopbackFixtureHost`, and `FixtureClient`,
plus a new `_CLIENT_ENDPOINTS` constant. The changed host methods were
`_disconnect_probe` and `_handle`. Shared `epoch_ms`, `SessionAuthority`,
`SessionCredential`, `TransportLimits`, `_Session`, `_response`, and
`FixtureLease` were AST-identical. PublicationTransport and BlenderClientTransport
delegate `_read_request` and `_send`; both methods were also AST-identical.
Replay service and reviewer use PublicationTransport/ReplayClient, not the
changed fixture client's execution path. This supports keeping the optimization
in the benchmark domain, but it cannot rewrite the historical whole-file maps.

## Restoration verification and preserved evidence

After the coordinator restored accepted `host/core/transport.py`, I repeated
all ten complete manifest joins over the 179-file union. No file was missing
or different. These are exact per-file SHA-256 comparisons:

| Original lane | Final comparison |
|---|---|
| `gt06-s79-http-complete-01` | backend 174/174 match |
| `gt06-s79-http-stop-01` | backend 174/174 match |
| `gt06-s79-saturated-stop-01` | backend 174/174 match |
| `gt06-s79-revoked-result-01` | backend 174/174 match |
| `gt06-s79-stale-capture-01` | backend 174/174 match |
| `gt06-s79-reviewer-complete-01` | backend 174/174 and UI 5/5 match |
| `gt06-s79-reviewer-stop-01` | backend 174/174 and UI 5/5 match |
| `gt06-s69-managed-replay-01` | runtime 159/159 match |

The restored transport is exactly
`1ec03356b1cb8c8987e1604bcb164aea6a9934dbe259451c19e12de36398aba0`.
The accepted GT05 manifest still has the file hash recorded above, and all of
its 143 declared source files match current bytes. The four S69 verifier pins
also match current `host/replay` files independently:

| Verifier | SHA-256 |
|---|---|
| `observation.py` | `f6ea8900f3c37737deef0c28387cd69f5f1bd5b13419333c75dfb0cd53e31a20` |
| `repair.py` | `dc1aa96c4f68633dcd22225d65f18609c294a7bd485b0b534d2096b36542ec07` |
| `repair_replay.py` | `3b8d842105ad4e1e5e55fc4a36e5a32e5095a462274144c4457c1fa4cdee5375` |
| `trace.py` | `8037b87d3a4ac51afc5504ac3105362f0211fa1519e68de32a32489166e9aaf5` |

Using pure path selection and hashing, with no runtime imports, I reproduced
the current `native_runner.sources()` and `PreparedPlay.prepare()` source
collector: accepted GT05 files, observed Godot/fixture suffixes, five explicit
native files, all `host/replay/*.py`, and the performance collector schema.
The resulting current backend map is exactly the historical 174-file map:
no added path, removed path or changed digest. In particular, no new replay
module is hidden by comparing only the old declared paths.

The native closure algorithm hashes sorted `path + NUL + digest + newline`.
The unchanged identities are:

- S79 backend 174:
  `644b90abfe769bf1a3654ba506cef50f8a38393f05f0be5ca7aae8050aaaa527`.
- S79 reviewer UI 5:
  `7665621f1090836c2bc711ccc7f6857c3961b99be5b077292baaadc933b712fb`.
- S69 managed runtime 159:
  `491b65875f8246e7606c7b860d9c61d6a85657fc0077075fa6dc7209128dca2b`.

There is no remaining changed dependency in these historical lane maps.
No native remint is needed on this source-delta basis. Preserve their original
source maps, evidence IDs and S69's S65 repair02 causal anchor; do not rename
or relabel the old executions as new runs.

## Benchmark bridge finding and fresh-proof boundary

The new `tests/replay/benchmark_transport.py` is a benchmark-local bridge over
the unchanged accepted transport. The observed module defines
`BenchmarkFixtureHost(LoopbackFixtureHost)` with a separate disconnect-test
mutex for arm/consume, and `BenchmarkFixtureClient(FixtureClient)` with a
sanitized local transport-failure observation. The command producer now imports
those benchmark classes under its existing factory names. This is a static
observation of work still being finalized, not a claim that differential tests
or a new HTTP probe have passed.

All three current benchmark source paths were explicitly looked up in every
historical backend, GUI and managed runtime map and were absent:
`tests/replay/benchmark_transport.py`, `tests/replay/benchmark_commands.py`, and
`tests/replay/run_benchmark_campaign.py`. No accepted runtime source was changed
to import this new bridge. The benchmark host still derives its admission,
journal/worker execution, Stop and socket handling from the accepted core;
the client has a small copied request method, so its wire/error equivalence
requires the fresh focused checks and regression coverage owned by the
coordinator.

The bridge and all actually loaded dependencies must be included in the new
benchmark freeze and post-run closure proof. The S81 141-test checks-01 and
HTTP probe01 remain historical diagnostic versions of the prior core edit.
They must not be described as observations of this later isolated
implementation. Checks-02 and HTTP probe02 were pending at this inspection;
this report makes no outcome claim for either.
