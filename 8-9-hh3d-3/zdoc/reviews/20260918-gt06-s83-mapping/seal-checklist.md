# Future GT-06 seal checklist — current 51-file/cleanup contract

AUTHORITY=0. NOT_FINAL. Not executed; no final seal, campaign PASS or critic
claim. Paths are relative to `8-9-hh3d-3/`. All items are terminal closeout
instructions, not permission to scan a running measurement or reuse failed
samples. Keep the original S81 failure sealed as failure evidence.

## 1. Eligibility and identities

- Obtain a completed ten-run campaign on a single frozen source/toolchain/
  profile. If source changes from `b3862a10`/51/
  `e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`, declare
  the new closure/count, affected dependency projection and fresh IDs; do not
  merely replace a digest in this draft. Do not combine partial attempts.
- Preserve profile
  `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`,
  toolchain-lock file SHA256
  `28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`,
  workstation identity, 7410s/run and fixed sampling/settling gates. Current
  `repair-source.json` includes `benchmark_transport.py`, both launchers,
  fixture modules and the perf schema; original S70 47/S80 47/50 maps are
  historical, not replacements for the current 51-file map.
- Confirm scheduler terminal state and no task instances before any full raw
  verification. Bind effective task XML/request/launch/principal/interpreter
  pins, registration/start/return and terminal status. Preserve actual
  supervisor-exit evidence when recorded; if absent, disclose it. `return.json`
  states its process exit is not yet observed and cannot fill that gap.

## 2. Per-run raw chain

- Retain `campaign.json`, `benchmark-profile.json`, frozen source copies and
  ten selected `run-NN-attempt-MM/` roots. Resolve context, source-files,
  toolchain, initial/project/native input manifests, import/host/editor owner
  captures, process-start/process-exit/cleanup/logs and every artifact reference
  to exact path, length and SHA256. Hashes are exact bytes; avoid newline or
  floating-point normalization. Keep excluded cache/raw locators explicit.
- Each run has one actual host/editor pair across all 35 ordered batches;
  five warmup batches remain in raw evidence and are excluded from metrics,
  followed by 30 measured. Every batch binds 1000 HTTP commands at 50/30/20
  mix, auxiliary Cancel receipt, 100 real native create/undo/save/reload cycles,
  ready/start/joint/ACK records, source/profile and PID/start-time identities.
- Preserve native index1.3.0 startup-readiness receipt and explicit synthetic
  focus delivery/blank roots with unchanged four-frame/1.1s settle. No claim
  of OS focus, tree clearing, counter correction or extra warmup. Verify scene
  file readback against each saved receipt rather than assuming unchanged
  initial serialization.
- Reproduce full raw latency/status distributions, schema counters and exact
  memory baseline semantics with frozen validators. Require inspect/Stop
  receipt p95≤500ms, status gap≤2s, declared RAM-growth limit≤10%, no lost or
  duplicate effects and no steady retained-resource growth. Preserve original
  RSS/timeout/ObjectDB failures; later prefixes cannot prove them fixed.

## 3. Mandatory child terminal cleanup for current successful runs

Use the executed `run_benchmark_campaign.py:verify_child_terminal_cleanup`,
whose current source digest is
`bb43ecc04c2de4872177a440eb071d533efdaa9e8194f62b4e0907bad8d4b252`.
The record is `child-terminal-cleanup.json`, schema
`hh-studio.benchmark-child-terminal-cleanup` version `1.0.0`. Do not retrofit
this schema into historical artifacts.

- Bind exact run/source/profile/context, 35 completed batches, `primary_error`
  null, `errors=[]`, `formal_acceptance=false` and actual observation time.
- Require stopped heartbeat, no retained constructor owner, both observer
  probes present with no retained/uncertain handles, closed producer, stopped/
  closing host, no host threads, both sockets closed, journal cache closed and
  index/database/directory detached.
- Require editor owner closed, drain threads stopped, actual helper PID and
  helper exit0 independently bound to its capture; compare Job/wrapper-handle
  observations with that capture. Preserve the distinct editor target PID.
- Editor/import target records must exist with matching start identities and
  actual exit0. Never derive a target exit from wrapper/helper result2, process
  disappearance or scheduler success. Keep failed/forced Stop cases labeled
  separately. Full-run `cleanup.json`, captured host/editor exits and released
  Job/handle observations must also pass the existing owner/assembly checks.
- Child record `host_actual_exit` and `supervisor_actual_exit` remain null by
  design because the child cannot observe them. Join host exit from the actual
  parent-owned receipt and supervisor status/exit from external observation;
  do not rewrite those child fields. Missing import wrapper-handle receipts or
  helper PID inventories remain explicit limits for the reviewer to assess.
- Retain the new record in the owned-run evidence map. Success-only
  `child-result.json` or `cleanup.json` alone does not replace post-finally
  cleanup, actual host exit or complete run verification.

## 4. Functional and fault reuse joins

- Resolve all 15 rows in `requirements.json`; catalog entries give concrete
  old paths and actions. Preserve S79 original IDs/backend174/UI5, S69 original
  replay159/verifier4 and S65 repair02 causal anchors. Recheck only affected
  dependency maps, including current path membership, after source changes.
  Do not run S79's historical whole453 verifier against unrelated changed
  benchmark files and misreport that as a functional regression.
- Resolve accepted GT05 manifest→actual consumed GLB→import/readback→real
  input/report/captures→S65 fault→typed repair02 receipt/selected config→S69
  managed replay. Match original hashes and command/run identifiers; a copied
  manifest hash without the chain is not final vertical-slice linkage.
- Keep S65 native runtime and S68 integrated GUI historical. Keep current
  collector/readiness/owner/test supplements separate, with their own executed
  driver sources, imported schema and source maps. Do not sum overlapping
  U69/U79/U80/U81 test totals or label unit injection as native proof.
- F11/F12 retain accepted S60 native OOM, S64 owned deadline/overflow/descendant
  cases and explicit bounded persistence/queue/Stop consumers. Preserve the
  physical-disk/power-loss/PID-recycle/multi-project limits from fault links.

## 5. Final review package

- Seal source, invoked tests/drivers/verifiers/schema, exact raw references,
  successful campaign/supervisor chain, failed-prefix history, all requirement
  joins, scope limits and reproduction commands in a final manifest. Keep
  source-closure, raw-file, profile-canonical and sample-evidence hash domains
  distinct. Verify Git bytes preserve executed logs/helpers (`-text` where
  required). Record clean source and all unexplained warning/error/leak gaps.
- Audit artifact completeness after measurement, not only copied reports.
  A selected-copy package must bind and locate excluded raw data. Repair a
  derived collector mistake from adequate original evidence while preserving
  executed helper/error bytes; do not rerun an engine merely to fix metadata.
- Two new independent critics must each give explicit PASS/TICK=yes for the
  same final manifest hash. Preparation, implementation preflight, self-checks
  and accepted GT01–05 signatures do not count. A later relevant source edit
  requires affected remint/review before coordinator acceptance.

The existing `s81-next/campaign-seal/verify_campaign_readonly.py.draft` is an
unexecuted proposal hardcoded to the failed S81 campaign. It is neither a
successful verifier run nor ready final proof for a future campaign ID.
