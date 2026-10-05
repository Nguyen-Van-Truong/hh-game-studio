# O6 observer direction closeout — 2026-10-01

This is a diagnostic decision note, not a gate change and not an acceptance
signature. Raw runs remain under `studio/.local/reviews/`.

## Evidence

- `gt06-o6-host-soak-20260930-02` completed 35/35 with child and wrapper exit
  0, clean Job/tree/handle, but O6.3 failed journal p95 timing: lookup
  `123.9876%` and append `120.4302%` of the first logical window. Private
  commit growth was `107.1151%`, so the variation trigger is also set.
- `gt06-o6-host-soak-20260930-03` stopped at batch 0 and
  `gt06-o6-host-soak-20260930-04` stopped at batches 0–8. Both are
  `HARNESS_FAIL` from `WATCHDOG_DOCKER_INVENTORY`; O6-04 records Docker
  inventory timeout at `2.219 s`, with closed zero-observed Job cleanup and no
  child exit record. They are not O6.3 results or `INFRA_ABORT`.
- O3 therefore exhausts this bounded direction at three attempts. A fresh
  O4.1 pass alone is insufficient justification for another 35-batch run.

## Options

1. **Recommended — environment-window retry after a bounded observer check.**
   Keep the two-second total observer budget and all O1/O4 thresholds. When a
   short read-only check returns quickly with validated Docker output, freeze a
   new source/profile closure and run one new O6.3 host soak by fresh ID. Cost
   is one short check plus one long run; risk is waiting for Docker Desktop's
   named pipe to be responsive.
2. **Repair the observer implementation.** Add a separately evidenced bounded
   named-pipe/query probe and its pure failure matrix, without using stale
   inventory to grant PASS. Remint the closure, rerun the short check, then
   consider O6.3. Cost is code and review work; risk is introducing a new
   harness boundary before formal.
3. **Defer O6 and continue O2.** Keep all four raw runs and the timing failure,
   finish O2's recovery/fixture/Blender work, then return after a clean resource
   window. Cost is schedule delay; risk is GT06 remains the dependency and no
   GT07 can open.

No option changes the O1 gate, timeout, watchdog classification, daily budget,
formal 2x35 requirement, or critic rule. Do not resume a terminal run, use a
partial prefix as PASS, or dispatch formal09 from this note.
