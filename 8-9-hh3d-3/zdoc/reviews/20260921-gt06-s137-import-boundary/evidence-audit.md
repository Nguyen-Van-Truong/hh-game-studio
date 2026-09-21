# S137 evidence audit: S134/S135/S136 import boundary

Audit date: 2026-09-21 (Asia/Saigon)

This is an independent, read-only audit of the S134 terminal packet, the S135
managed-boundary packet and raw probes, and the S136 plan/packet metadata. I
read JSON, text, directory listings, and selected file hashes only. I did not
launch Godot, Docker, tests, or any runtime worker, and I did not modify plan
or product source.

## Result

The material remains diagnostic evidence with zero accepted GT06 full runs. It
must not be described as an exact-copy packet, a clean process run, a completed
engine workload, or an environment root-cause finding. The raw observations are
useful, but the packet metadata needs the corrections below before a later
bounded run is compared with it.

## Findings

### 1. S134 packet is an index to external raw files, not 1,019 exact copies

`20260920-gt06-s134-validation-boundary/terminal-packet-01/` contains only
`analysis.json` and `manifest.json`. The manifest lists 1,020 records (the
reported 1,019 raw records plus one derived analysis record), but each record
has a `source` path under the sibling managed-review tree or `.local` tree and
only a SHA-256 and size. There is no `managed/`, `owned/`, or other materialized
raw copy below `terminal-packet-01/` itself. `authority=0`,
`formal_acceptance=false`, and `raw_preserved=true` do not change this custody
boundary. The packet can be verified against currently present external paths;
it is not self-contained exact-copy evidence.

### 2. S135 has a stale digest and a circular manifest reference

The current bytes of
`20260920-gt06-s135-managed-boundary/terminal-packet-02/manifest.json` hash to
`9a9a06331cf51afe3ace62f22ff4649ad951836693f1b2ababd1d7fc7f11f27d`. However,
`static-attribution.json` records the manifest hash as
`896cb1031928b9eec2bdbf13dcceae704a98f0a7375feeff745f163a45852023`.
That assertion is stale relative to the sealed packet bytes. At the same time,
the manifest includes `static-attribution.json` as one of its entries (with
hash `e6203e...`). A verifier cannot treat both the manifest digest inside the
static report and the static report digest inside that manifest as one
mutually-closed hash chain. `missing=[]` only says the referenced paths were
present when checked; it does not repair the stale/circular digest or turn the
manifest into a payload copy.

### 3. “Not an engine run” is too broad for the S135 profile probes

The S136 plan says S135 was “not an engine run.” The two raw profile probes,
`gt06-s135-profile-boundary-03` and `-04`, contain actual Godot output:

* `Godot Engine v4.7.2.stable.official.ed1daf0bf` is printed;
* `parse` completes with code `0`;
* the `import` phase starts, performs filesystem/editor initialization, and
  ends with `HH_PROFILE_PHASE_END import -9`;
* the host/container result is exit `45`.

Thus an engine process did run and reached import. What was not reached was the
readback/command workload and a successful phase sequence. The precise claim is
“Godot process observed through parse and import; SIGKILL during import before
readback/command workload; diagnostic only.” The managed repair is a separate
case: it stopped before command/owner creation at `VALIDATION_PHASE_ORDER`.

### 4. Matching bundles show reproducibility, not an environment cause

Probes `-03` and `-04` use the same bundle manifest hash
`59d82989f9590b0842ae87a74fff6aa20db8cde6ddc0039dfa0824d0fc745e96`, the same
source-closure hash `9114ed69a9b8905be4681c04650fc01be26a53a164598dea92c1942ce6e4b25f`,
the same toolchain/image/binary hashes, and the same 11-file profile manifest.
Both reproduce the import boundary. This supports “same setup, same observed
boundary”; it does not distinguish an environment cause from a deterministic
input/engine/runner interaction. Both probes are `formal_acceptance=false` and
`public_ack=false`, and the packet records `root_cause=unknown`. A changed,
controlled boundary is required before environment attribution.

### 5. Actual exits and cleanup are narrower than a generic “clean” summary

The S135 managed raw records show the outer owner target PID `45112` exiting
`1`, wrapper PID `45272` exiting `0`, `tree_verified=true`; the nested child
record shows target PID `14152` exiting `1` and wrapper PID `47264` exiting `0`.
`repair-terminal-cleanup.json` reports `known_editors=[]`, `attempts=[]`,
`owner_closed=true`, `transport_closed=true`, and `cleanup_clean=true`. Because
validation failed before owner/editor creation, this is owner/transport
cleanup after a pre-command rejection, not an editor or engine natural-exit
record.

For the S135 profile probes, the container state is exited with code `45`,
`Pid=0`, `Running=false`, and `OOMKilled=false`; the Docker job/handle is
reported zero/closed and owned files were removed. But each probe also records
`diagnostic_process_clean=false` with
`EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN`. That flag must remain visible; “job zero /
closed” is not equivalent to a clean engine/process result.

S134's raw analysis similarly records outer target PID `26188` exit `1`, wrapper
PID `46824` exit `0`, and `tree_verified=true`, while
`successor_close=MISSING` and `successor_natural_exit=UNKNOWN`. Its two
validation containers exited `0`; that does not supply the missing successor
editor/engine exit proof.

## Proposed metadata correction (no source or plan mutation in this audit)

1. Label packet custody explicitly, for example:
   `packet_kind=manifest_plus_external_raw_refs`,
   `payload_mode=external_source_refs_only`,
   `materialized_exact_copy_count=0` (inside the packet directory), and
   `indexed_external_record_count=1020` for S134. Keep the existing source
   paths and hashes as an index; do not call them exact copies.
2. Break the S135 hash cycle. Freeze the payload/index manifest first, record its
   final hash in a separate attribution record, and then hash the attribution
   record from a wrapper/checksum file that does not itself belong to the
   frozen manifest. At minimum, mark the current `896cb...` field as
   `stale_manifest_sha256` and do not assert `manifest_complete=true` while it
   disagrees with `9a9a...`.
3. Split phase and workload fields: `engine_process_observed=true`,
   `engine_phase_reached=import`, `readback_reached=false`,
   `command_lane_reached=false`, and `formal_acceptance=false`. Keep
   `managed_precommand_validation_rejection=true` for the managed route.
4. Keep cleanup scope per attempt: `owner_transport_cleanup_clean=true` only
   for the managed pre-command record; preserve
   `diagnostic_process_clean=false` for both profile probes and retain the
   actual target/wrapper/container exit records. Add explicit
   `successor_exit_known=false` where the raw record is missing/unknown.
5. Replace environment-causal wording with
   `same_bundle_boundary_reproduced=true` and
   `environment_root_cause_proven=false`. This keeps the useful S135
   reproducibility observation without converting it into attribution.

These corrections preserve the raw evidence and do not alter the GT06 gate,
timeout, baseline, or acceptance criteria.

## Read-only checks

* Listed the S134/S135 packet and raw directories and confirmed packet payload
  counts.
* Parsed the S134 analysis/manifest, S135 analysis/manifest/static attribution,
  both S135 probe records, and the managed cleanup/owner records.
* Recomputed selected hashes for the packet metadata and compared the recorded
  exit/cleanup fields. No engine, Docker, test, or mutating command was run.

