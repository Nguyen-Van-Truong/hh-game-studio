# S228 — phase-correlated RSS provider differential

S228 is an Authority0 diagnostic, not a GT06 acceptance run. It runs one
bounded native cycle and compares the campaign-internal RSS sampler with an
independent retained-handle `ProcessProbe` attached to the same editor PID.
The comparison is phase-correlated by monotonic host timestamps; it does not
replace the formal 10-pair × 35-batch gate.

The observer collected 440 external samples and 373 internal samples, with
373 comparable pairs and a median relative RSS difference of `0.0`. The
maximum timestamp pairing delta was 13,899 microseconds. The native editor
exited with code 0, import exited with code 0, and the captured Jobs were
zero/closed with handles released. The raw native capture and process metrics
are referenced by hash in `internal-references.json`; they remain in the
separate native diagnostic directory and are not merged into this packet's
manifest.

The result shows provider agreement for this bounded native cycle, while
explicitly proving neither a measurement defect nor a leak owner/root cause.
It therefore permits a fresh formal ID to be prepared under the existing
timeout, baseline, profile, retained-counter and +10% RSS gates. It does not
change those gates, open GT07–GT10, or turn any partial/diagnostic result into
acceptance.

Raw packet: `studio/.local/reviews/gt06-s228-phase-rss-01`.

- Raw manifest SHA-256: `1410e8116c2279a1c9f991233bbe5cf4e2ee058f7ab3d68742692ebfa63b4ec1`
- Sealed archive SHA-256: `75941c6e4ecf94b0094b6eb7da9807a15f917baa0541e2bcf7ef86ef0b78bdd5`
- Raw files: 8
- Run ID: `gt06-s228-phase-rss-01`
- Native diagnostic ID: `gt06-s228-native-cycle-01`

Run `python -B zdoc/reviews/20260924-gt06-s228-phase-rss/verify.py` for
engine-free verification of the packet and its sealed raw manifest.
