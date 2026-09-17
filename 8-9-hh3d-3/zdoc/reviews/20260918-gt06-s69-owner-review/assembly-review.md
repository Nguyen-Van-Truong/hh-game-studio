# GT-06 assembly compatibility and provenance review

Date: 2026-09-18, Asia/Saigon. Reviewer: `assembly_review_final`.

Reviewed commit: `c5e56c7e05e5bf784d1e67741cd44cd18b6bd493` (S68).
This S69 review-directory name does not imply an S69 source commit or acceptance.
Read nested `AGENTS.md` and the current GT-06 tools plan. Review scope was
`benchmark_assembly.py` against command producer v1.1 and native producer v1.2;
the profile and campaign wrapper were inspected to establish the call boundary.
No tests, engines, subagents, or runtime/source edits were performed. This report
is the only file written by this review. No formal acceptance or TICK is issued.

## Result

No deterministic rejection of normal producer output, or demonstrated
campaign-03 false PASS, was found. Command field shapes, lookup/Cancel accounting,
native operation timing, separate host/Godot clock domains, and ready/start/ACK
bindings match the reviewed producers. This is a bounded static finding, not
proof that the ongoing benchmark completes or meets performance thresholds.

## Finding: standalone dataset assembly loses checkable run provenance

**P2, library boundary; mitigated in the current campaign call path.**

`benchmark_assembly.py:553-554` verifies each run's frozen source closure and
toolchain artifact. However, its return at lines 650-652 omits those explicit
hashes. The source hash contributes to each sample's opaque `evidence_sha256`
(lines 509-520), which cannot be decoded to recover that provenance.

`assemble_dataset()` at lines 655-658 consequently accepts ordinary run
dictionaries and a separate caller-provided provenance dictionary without
comparing their source/toolchain origins. `benchmark_profile.py:170-172` checks
only the syntax of these provenance hashes. Ten otherwise valid, distinct runs
assembled independently from different source closures can therefore be combined
under one declared source hash. If their measurements meet the thresholds, the
profile summary can report measurement PASS despite that provenance mismatch.
The same missing comparison permits a wrong declared toolchain hash.

This is a static API-level counterexample, not an executed reproduction or an
observed corruption of campaign-03. The API currently cannot independently
prevent accidental mixing after callers retain only its returned run dictionaries.

### Why the current campaign is protected

`run_benchmark_campaign.py:287-310` freezes one source dictionary/digest and rejects
resume if the frozen campaign, source, or workstation differs. Fresh run manifests
use that same digest at lines 380-382. `verify_run_capture()` checks the captured
run and context against the expected digest at lines 245-256, the child at lines
267-272, and captured owner/source evidence at lines 229-241 and 283. Both fresh
and resumed runs pass that verifier (lines 401-402 and 330-334).

Thus the reviewed production wrapper supplies the invariant that the standalone
assembly API lacks. No current-campaign blocker is established by this finding;
do not interrupt campaign-03 or relabel its results solely because of it.

## Minimal hardening proposal, report only

Keep the strict benchmark profile JSON schema unchanged. Carry provenance in an
internal checked run envelope rather than adding fields to profile run objects:

1. Have the strict assembly path return a `BoundRun` containing canonical run
   bytes and verified `source_closure_sha256`, `toolchain_sha256`, and
   `profile_sha256`. Use immutable bytes plus a content hash, or defensive copies,
   so a mutable run dictionary cannot silently change after binding.
2. Require these envelopes in the strict `assemble_dataset()` path. Compare every
   envelope's source/toolchain/profile hashes against dataset provenance and the
   expected profile before unwrapping its existing run value for
   `profile.validate_dataset()`.
3. Update the campaign's serialization handoff to explicitly write the unwrapped
   existing run JSON. If a compatibility entry point accepting plain dictionaries
   is retained, distinguish it from checked/native assembly; it must not bypass
   the provenance requirement implicitly.

This proposal checks provenance equality; it does not turn hash-bearing Python
objects into independent execution attestation. Preserve the outer owner/exit,
capture-manifest, source, and workstation verification. No changes to workload,
thresholds, process-count requirements, or acceptance rules are proposed.

When implementation is authorized after the current diagnostic, focused checks
should reject mixed-source runs, mixed-toolchain runs, wrong declared provenance,
plain unbound dictionaries, and run bytes changed after binding; one matched
envelope set should still produce the unchanged strict profile JSON. None of
those tests was added or executed during this review.

## Exact reviewed file hashes

Paths below are relative to `8-9-hh3d-3/studio/`. Hashes are SHA256 of the files
read from the workspace. HEAD remained the commit above and `git diff c5e56c7`
reported no changes for these five files when the hashes were captured.

| File | SHA256 |
| --- | --- |
| `tests/replay/benchmark_assembly.py` | `d2f9587774c42357c85182fcad27ed2d16db26192b6ef25eaa4b28a2763f34bd` |
| `tests/replay/benchmark_commands.py` | `522e91341eda6175704b692cd9bc5454951f93a891657e815a9a2111cd3eb438` |
| `tests/replay/benchmark_native.gd` | `da0bb949ebaf3bc3881a1e9ad325d98ac6496fc3a0454b825a28655fdbc37515` |
| `tests/replay/benchmark_profile.py` | `ddbd98583060f791226fca83e275cf01204b37112627383198dcef4ec6f6f233` |
| `tests/replay/run_benchmark_campaign.py` | `cd22296437e1b73e9521f95593a76d097623d80393bd0c55f214494ef4ed532d` |
