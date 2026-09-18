# GT-06 requirement map draft

`AUTHORITY=0`; `STATUS=NOT_FINAL`; source closure target is
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.

| Requirement | Existing evidence | S81 status | Final condition |
| --- | --- | --- | --- |
| Real play/input/observe path | S79 backend + GUI maps | dependency retained | same frozen closure plus full campaign map |
| Pause/Stop and response-loss semantics | S69 runtime/replay maps | dependency retained | actual target/helper exits and Stop inventory |
| Journal/HTTP admission and cleanup | S81 admission 204/204, HTTP02 supplemental | diagnostic only | affected lane remint and strict terminal verification |
| Native counters and quiescence | S81 campaign `r00.a01` | **FAILED** at batch15, +2 ObjectDB | bounded owner diagnosis, new closure/campaign, 10×35 terminal PASS |
| Source/profile/workstation binding | S81 51-file closure and profile | frozen | final manifest rehashed before critics |

Partial S80/S81 samples, supplemental probes, and scheduler state are never
substitutes for the final dataset. This map deliberately leaves GT-06
`IN_PROGRESS` and does not authorize GT-07.
