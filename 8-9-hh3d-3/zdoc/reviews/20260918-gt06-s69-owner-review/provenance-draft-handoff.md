# BoundRun provenance hardening draft

Status: DRAFT ONLY, NOT APPLIED, NOT TESTED. No engine or test was run. The
draft-generation command only read source text and wrote patches/metadata into
this review directory; it did not import or execute benchmark modules.

Base: `c5e56c7e05e5bf784d1e67741cd44cd18b6bd493`. Exact input, proposed-result,
and patch SHA256 values are in `provenance-draft-manifest.json`.

## Files and integration

- `bound-run-provenance.patch`: adds the small `BoundRun` envelope, binds it at
  the end of `assemble_run()`, and checks source/toolchain/profile agreement in
  `assemble_dataset()` before passing unchanged run dictionaries to the profile.
- `bound-run-regressions.patch`: updates the existing full raw-run assembly test
  for the envelope and adds seven synthetic regression methods covering matching
  provenance, mixed provenance, wrong dataset provenance, unbound dictionaries,
  changed bytes, detached readback, and malformed envelopes.

The campaign hunk is deliberately exactly one changed statement:

```python
write(output / 'assembled-run.json', assembled.value['run'])
```

The coordinator has since integrated owner handle proof and is adding the
run-specific stop-request channel. Apply the campaign statement manually over
that newer file; do not replace the live campaign with an older complete copy.
The manifest's proposed campaign hash describes only this one-line change on
the recorded c5 base, not the final integrated campaign.

## Binding and compatibility

`BoundRun` hashes immutable JSON bytes containing exactly the existing `run`
plus `source_closure_sha256`, `toolchain_sha256`, and `profile_sha256`. Provenance
and run bytes share the hash, so modifying either without rebinding fails.
Reading `value` returns a detached parsed envelope. The outer process/capture
verifier remains required: this container prevents accidental mixing, not
forgery by a caller that constructs and hashes invented evidence.

The verified source closure and toolchain artifact hash come from each run's
original manifest/artifacts. The profile hash comes from its already checked
profile bytes. No current-workspace hash replaces the captured source hash.
All six batch artifacts, producer versions, run-manifest schema, sample evidence
hashes, and final profile schema remain unchanged.

Accordingly, legitimate complete raw packages from one older source closure can
still be reassembled together using their original manifests and matching dataset
provenance. The draft adds no check requiring a frozen verifier copy to equal the
currently loaded verifier. Persisted `assembled-run.json` retains its old strict
run shape. The campaign already reconstructs dataset inputs from raw/manifests,
so resume does not need to trust or auto-wrap old unbound run dictionaries.

Changing the live implementation changes the source closure for future native
runs. Preserve existing raw files and their original provenance; do not relabel
old evidence as the new source or join incomplete batches across sources.
Per coordinator status, campaign-03 has one valid batch followed by controlled
Stop, not a full PASS or a complete run accepted by this API.

The new serialization/checks execute during offline full-run/dataset assembly.
The per-batch `assemble_sample()` and both measured producers are unchanged.

## Validation still required after integration

No test result is claimed. After integrating the isolated hunks, run the focused
assembly regression file and relevant campaign handoff tests once. The existing
full raw-run fixture must still assemble with its original schemas, while one
complete run must still fail the ten-run dataset requirement. The new matched
ten-run synthetic case must yield the exact unchanged profile dictionary;
mixed source/toolchain/profile cases must fail before profile validation.

Seven new regression methods are proposed, not seven observed passes. No
threshold, workload, quota, engine pin, raw-evidence version, or acceptance rule
is relaxed by this draft.
