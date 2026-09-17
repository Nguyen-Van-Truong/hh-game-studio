# S73 final sealing preparation

Preparation only. This new folder rebinds the historical S71/S72 draft to
`gt06-s73-campaign-01`, source commit `cb4d1f6f`, 49-file benchmark source closure
`6f5d4c8a14ef8476c4cff6afb06ab161b17905f8593f9a685cd235593d7ee913`, and unchanged
profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
Paths below are relative to `8-9-hh3d-3` unless explicitly stated otherwise.

The active campaign was not queried or validated during preparation. No
engines, tests, raw-tree scans, source/plan edits, staging, or acceptance actions
were performed. The old seal draft remains unchanged. Its input hashes,
syntax/equality checks and limited S72 reviewer observations belong to that
historical draft and are not checks or signatures for this new adapter hash.

## Draft contents

- `collection-recipe.json` carries the original collection/ownership/BoundRun
  rules with S73 campaign, source, checkpoint and adapter bindings. It retains
  the exact 10 fresh process pairs × 35 batches, workload, counters, thresholds
  and 7410-second per-run limit. It is not a final manifest.
- `affected-dependency-bridge.json` adds the S73 focused-validation package and
  all five reminted service lanes, including original raw paths, owner captures,
  differing source-map domains and remaining per-lane comparisons.
- `verify_campaign_readonly.py.draft` retains the inherited strict JSON/profile
  and existing validator calls. Only campaign/source/report bindings and
  explicit remaining work were adapted. It is **unexecuted**, including syntax
  parsing. Its expected commit field is not a Git verification result.
- `preparation-inputs.json`, `draft-check.json` and `draft-review.md` distinguish
  preparation reads from historical reviews and pending final verification.

Do not execute the adapter, the checkpoint helper, or a full evidence hash pass
while measurement is active. Do not use the campaign runner's main entrypoint
as a read-only verification command: it can launch or resume native work.

## S73 dependency bridge

The bounded commit-path comparison from `bb881a4a` to `cb4d1f6f` found one
changed studio file, `host/replay/verified_journal.py`. Its private cache
fingerprint now uses SHA512. The accepted journal/transport, persisted record
checksums, wire digests, source/evidence SHA256, full-byte validation and fsync
contract retain their existing roles. Both benchmark commands and
`ReplayService` consume the changed module.

The recorded recovery package contains 382/382 replay unit results and a
30-inspection HTTP diagnostic over an exact private copy of the failed S71
history. The copied-history diagnostic reports terminal p95 282.0598 ms,
maximum response gap 166.111 ms, exactly 60 new records, preserved original
bytes/prefix and actual exit 0. These are recorded inputs, not results rerun or
audited by this preparation, and they do not replace the benchmark.

The five remints are:

| Lane | Run ID | Recorded checks | Native exit interpretation |
| --- | --- | ---: | --- |
| HTTP complete | `gt06-s73-http-complete-01` | 96 | Natural native exit 0 |
| HTTP Stop | `gt06-s73-http-stop-01` | 12 | Intentional Stop; no natural exit claim |
| Saturated Stop | `gt06-s73-saturated-stop-01` | 15 | Intentional Stop; no natural exit claim |
| Revoked result | `gt06-s73-revoked-result-01` | 18 | Natural native exit 0 |
| Stale capture | `gt06-s73-stale-capture-01` | 17 | Natural native exit 0 |

`zdoc/reviews/20260918-gt06-s73-recovery/service-remint/verification.json`
records 158 checks and 1,281 raw files / 43,962,707 bytes. Its hash recorded in
`focused-validation.json` is
`f29b942a9dd84fe9c73e6e537650f57fab2fd40470ac3dce870f7e7fa86de1d5`.
Preserve the original actual exits and closed/zero Job captures. The two
intentional Stop lanes retain `native_actual_exit=null`; outer exit 0 cannot
be promoted to natural native exit 0.

The benchmark map has 49 files, the remint review runner map 148, and each
remint runtime map 173. These are distinct dependency domains. The named
changed-file value matches across the inspected maps at
`9128749e6a04242106e56a86e959b6de0a67e0f10ffb97965e1bc88390d5a6f2`.
This observation is not a full map or raw-byte audit. Final sealing must compare
each complete lane map and enumerate changed, added and removed dependencies.

Older S68 GUI/runtime and S69 service evidence therefore cannot be labelled
exact-current S73 source. Preserve its original maps and use the new bridge
only for the changed journal/service dependency. Check the unchanged GUI and
trace dependencies separately; a missing requirement edge remains a gap.

## Causal provenance stays original

Retain the original chain: S65 seeded fault (`gt06-s65-native-04`) → authenticated
GT03 repair (`gt06-s65-repair-02`) → S65 replay (`gt06-s65-native-05`) → S69 managed
replay (`gt06-s69-managed-replay-01`). Keep the original trace/configuration,
command IDs, repair02 receipt, before/after hashes, captures and driver records.

The S69 replay's source closure remains
`491b65875f8246e7606c7b860d9c61d6a85657fc0077075fa6dc7209128dca2b`; its capture hash
remains `d2f4985f75d6017e8ce13078d69973b9c7294a2719748cc978ba0977c0e6d0e5`.
The selected configuration remains
`4fe3141b9afe6b411b585b203cebae77e851a406c291ac26620eb8cd7c018d90`.
The S73 bridge does not rewrite or re-sign these earlier observations.

## Finalization after terminal measurement

1. Collect terminal scheduler status and every actual launch's supervisor
   request/XML/registration/start/return/log chain before task deletion. A
   supervisor return or scheduler result cannot replace target/helper exits.
2. Reuse the existing
   `zdoc/reviews/20260918-gt06-s71-growth/verify_source_checkpoint.py` helper with
   revision `cb4d1f6f` and an exclusive new report path. The existing S73 index
   report says `revision=index`; do not relabel it as named-commit proof.
3. Review the new adapter and run it only after terminal artifacts exist, with
   the campaign-pinned Python, final scheduler status and actual launch number.
   Capture the verifier's real exit/stdout/stderr. It delegates selected-run
   capture/ownership checking, `BoundRun` assembly and unchanged profile
   validation; it does not itself seal GT06.
4. Hash the complete selected campaign and all explicitly referenced inherited
   raw/review files. Bind S73 focused validation and all five service remints;
   retain separate source domains, owner records, expected negative evidence,
   skipped tests and excluded attempts. S71 remains FAILED: its 33 completed
   batches and failed prefix are never S73 samples. Do not sum overlapping
   historical unit suites.
5. Resolve F01–F15 with exact requirement/test/source/evidence references and
   the scoped S73 dependency bridge. Preserve S65/S69 causal provenance and
   GT05 accepted producer/import bindings. Snapshot mutable governance files;
   freeze source, review, raw and any portable view in separate hash domains.
6. Provide two independent read-only critics the identical final candidate
   manifest hash and physical raw locator. Critic reports stay outside that
   manifest to avoid circular hashing. New candidate/source bytes require new
   reviews; coordinator acceptance remains separate.

Write allowlist for this preparation: only
`zdoc/reviews/20260918-gt06-s73-next/seal/`. No acceptance or critic verdict is
issued here.

Coordinator follow-up: `coordinator-static-check.json` records a syntax-only
AST parse and generated JSON readback. The recipe's full49-file map and profile
equal the saved startup copies. The adapter was not executed; no live raw
validation, tests or engines ran. This later check does not alter the worker's
earlier `NOT_RUN` record or constitute final evidence verification.
