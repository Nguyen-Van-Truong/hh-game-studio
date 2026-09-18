# GT06 S86 failure packet — ObjectDB growth at batch 17

`AUTHORITY=0`; diagnostic/failure evidence only. This packet is not an acceptance package and its partial prefix must not be used as a benchmark sample.

The scheduler-owned campaign `gt06-s86-campaign-01` (source checkpoint `b3862a10`, 51-file closure `e010180a…`, profile `0cd5b530…`) stopped at batch 17 during `joint_observation` with `CAMPAIGN_RETAINED_COUNTER_GROWTH`. The observed ObjectDB count changed `71128 → 71130`. Editor held handles were `568` at the first capture and `555` at batch 17, resources stayed `6`, and RSS fell from `753299456` to `162512896` bytes. Batch 17 had no dropped commands or telemetry and a `735.9644 ms` maximum status gap.

Cleanup recorded Job zero, closed owner and released handles. The host exited `1`, the import target exited `0`, helper exited `2`, while editor target and supervisor actual exits were not recorded. Do not infer natural exit or PASS from the missing records.

This packet preserves selected exact raw receipts and hashes. The next step is a bounded identity-level attribution diagnostic under the unchanged source/profile; do not relax the ObjectDB gate or launch another full campaign until that diagnostic and cleanup are complete.
