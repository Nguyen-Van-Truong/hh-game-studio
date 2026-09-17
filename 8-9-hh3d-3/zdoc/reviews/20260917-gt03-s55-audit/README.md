# S55 Godot candidate audit

This directory is evidence, not the tools plan or an acceptance verdict.
The authoritative state remains `../../8-9-godot-blender-agent-studio-plan.txt`.

The immutable 176-file runtime and unit snapshot is
`../20260917-gt03-s55-source-01`, closure
`3a220b51105166274bad4bde950f4cc1d975e87b009b66e52428fad9dc27b02e`.
The complete unit matrix ran **699/699**, with actual successful target/wrapper
exits and empty owned process trees. The additional four native inspection
tests overlap that inventory and are not four additional distinct unit tests.

`run_native_lane.py` runs one bounded native lane over this snapshot.
`run_drained_publication_lane.py` is an explicitly separate cleanup-only test
driver for script/save. It waits for the existing durable Stop contract before
closing the owner. It changes no runtime/unit byte or operation deadline. Its
exact generated driver, original probe, controller, invocation and effective
execution map are retained with each run. Script01's target exit 1 remains a
failed harness run; script02 is the separate completed replacement.

`verify_semantic_evidence.py` independently checks raw process exits, selected
bytes, responses, engine observations, event folds and native custody exports.
It emits a portable manifest and a separate **effective execution closure**
covering the runtime plus actual external drivers and their dependency maps.
Do not confuse that review-target hash with the 176-file runtime hash.

An audit exit 0 means the available evidence is internally consistent. It is
**not completion** unless `all_requested_evidence_complete` and the effective
manifest's `all_native_lane_maps_present` are both true and all remaining gaps
are empty. Two independent critics must review the final effective closure
before the coordinator may accept GT-03.

Native exports are non-publishing content verification with write-capable
verification handles. They open existing stores, verify before/after bytes and
identities, and close owned handles; they do not append, rearm or publish.
Portable hashes preserve those observations, not Windows ACL/Registry authority.
Engine, Linux, exporter and native journal integration runs share one serialized
coordinator slot. File-only audits can run concurrently.

Reproduction from the repository root (use fresh output directories):

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-audit/verify_semantic_evidence.py --output 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-audit/semantic-new
python -B 8-9-hh3d-3/zdoc/reviews/20260917-gt03-s55-audit/test_semantic_evidence.py
```

`checkpoint.py` curates only tested source and explicitly supplied portable
manifests, then compares exact Git index/HEAD blobs. The S55/read-client WIP
checkpoint is `4b10c53`; `checkpoint-02` verified 1,482 files. It excludes new
untested modules, private storage, transient `.writer` guards and caches.
Historical Blender manifests that include such guards are not silently packed
or presented as complete portable manifests by this checkpoint.
