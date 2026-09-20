# S129 fresh diagnostic — pre-engine Windows Job boundary

`AUTHORITY=0`; this packet is diagnostic-only, excluded from F13/F14 and from
GT06 acceptance. Run `gt06-s129-host-attribution-02` was dispatched with the
unchanged S129 runtime source closure `aa67729efc7ce45a5c94843f01ad1c7f823f51987574b80e15cfaf8c66a4d65b`, runtime checkpoint `d97960f3`, native source hash `13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95`, and profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

The stock launcher failed before batch 0 while configuring the Windows Job:
`BENCHMARK_JOB_LIMIT_MISMATCH`. It requested `job_time=72000000000` (100-ns
units) and Windows returned `72000156250` (+156250); flags, active process
limit and memory matched. No Godot/editor/native benchmark process started and
there are no samples or gates. The retained launcher exited 1; import target
exited 0; child helper exited 2; outer helper exited 1. The owner Job was
closed with zero active processes and all recorded handles were released.

This is a pre-engine environment boundary, not a status-gap, transport result,
handle-leak finding, memory result, or root-cause proof for S127/S128. S126's
read-only five-row probe remains the attribution reference: four exact
readbacks and one identical +156250 rounding result, all owners closed. Keep
the strict equality gate. Do not change timeout, gate, baseline, profile or
source, and do not rerun formal GT06 until a read-only attribution decision is
made. A fresh diagnostic ID is required after any new dispatch.

The copied receipts are byte-exact selected evidence. Local `.local` raw trees,
cache, journals, secrets and unrelated untracked history are intentionally
excluded. `reference/s126-job-readback-probe.json` and
`reference/s126-job-configure-readback.json` are byte-exact attribution
references. `manifest.json` records the selected file hashes and this packet
is not eligible for the GT06 dataset.
