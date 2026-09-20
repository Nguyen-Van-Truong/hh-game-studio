# S127 full stock diagnostic — host retained-counter boundary

`AUTHORITY=0`; diagnostic-only and excluded from F13/F14. This is not a
formal GT06 PASS and does not prove a leak or root cause.

The fresh stock run used the unchanged S125 candidate source closure
`6d580e30e6d9368a5118749687589e4893fc5b88bcaf6b0af4414ce15ce91fc2`, the
unchanged profile
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`, the
original native hash
`13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`, and
run id `gt06-s127-post-failure-full-01`. The Job readback passed, so the
stock engine actually ran; no source, profile, timeout, baseline, threshold,
priority, or RSS policy was changed.

The run completed batches 0–17 and durably recorded the original gate failure
at batch 18 (`joint_observation`): `CAMPAIGN_RETAINED_COUNTER_GROWTH` because
the resident Python host's held-handle counter changed from baseline `209` to
`210`. The same sample reports editor handles `559` at baseline and `555` at
batch 18, editor objects `71130` and resources `6` (unchanged), host RSS
`56,786,944`, editor RSS `759,185,408`, and maximum status gap `543.228 ms`.
HTTP transport failures were zero and no accepted dataset row exists. The
19 partial batches stay outside the formal dataset.

Cleanup evidence shows the owner Job closed with zero active processes and no
retained handle; producer sockets/journal and owned threads were cleaned. The
parent recorded host/editor target exit code `1`; the child terminal record
keeps editor natural exit as `UNKNOWN` rather than inferring it from a
scheduler state. These gaps remain preserved.

The previous S127 helper watched only the editor counter, so no supplemental
post-failure snapshot was emitted for this host-side rejection. That is an
observer coverage gap, not a pass. The copied diagnostic helper now contains
an explicit host observer and `host_observer_selfcheck.py` passes; the
`post_failure_full.py --check` read-only preflight also passes. No engine was
rerun after the failure. A future fresh diagnostic may use this helper only if
host attribution is still needed; do not weaken the original gate or merge
this partial run into F13/F14.

The derived `host-counter-attribution.json`/`.md` report reads only the 19
preserved sample files. It shows the host counter stayed at 209 through batch
17 and changed to 210 only at batch 18; host RSS stayed within the original
limit, while the editor counter was lower than baseline. This narrows the
boundary but does not identify a kernel object or a leak.

Selected raw artifacts are copied byte-for-byte beside this README. The
manifest covers only this review packet and excludes the large local runtime
tree, caches, journals and secrets. `s126-plan.snapshot` is the byte-exact
predecessor plan; failed raw data remains under
`studio/.local/reviews/gt06-s127-post-failure-full-01`.

Fresh ID after S126 Job readback attribution. Static five-process probe showed 4 exact reads and 1 transient +156250 unit readback. Keep strict Job gate, original profile/native source and no dataset. The helper captures handles/PSS only after an original retained-counter rejection.

