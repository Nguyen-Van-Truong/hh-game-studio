# GT-06 S90 low-overhead lifecycle attribution diagnostic

AUTHORITY=0. This is a disposable diagnostic overlay, not a campaign and not acceptance evidence. It samples only ObjectDB at the ACK `FileAccess` close boundary, after the local reference is set to null, and after the validated fresh ACK counters. It removes S88's reachable-tree census to avoid changing RSS and timing. The base 51-file source closure, profile, campaign thresholds, and 10x35 acceptance contract remain unchanged.

A full run is allowed only after preflight `gt06-s90-lifecycle-attribution-preflight-06` verifies the overlay. The supervisor now emits `diagnostic-manifest.json` only after nested target/helper exits, Job zero/closed and cleanup receipts are independently present. Preserve any failure, actual exits, Job/handle cleanup, and manifest; never splice a diagnostic into GT-06 PASS.
