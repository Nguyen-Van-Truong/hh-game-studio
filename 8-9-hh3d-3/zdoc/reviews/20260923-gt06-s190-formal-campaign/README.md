# GT06 S190 terminal packet

gt06-s190-formal-01 is a fresh formal attempt under the frozen GT06 contract. It completed 11 batches (warmup 0–4 and measured 5–10) and failed during joint observation for batch 10 with CAMPAIGN_RETAINED_COUNTER_GROWTH.

The frozen baseline after batch 4 had editor handles 555. The batch-10 sample had 557; host handles stayed 204, editor ObjectDB/resources stayed 71128/6, and editor RSS decreased. HTTP phase evidence records zero transport failures. This is a retained counter boundary and failure evidence only: it does not prove a leak, ownership, root cause, or GT06 acceptance.

Cleanup recorded the host wrapper exit 1, import exit 0, closed Job/owned tree zero, and no retained wrapper handle. The editor target exit was not independently recorded and remains UNKNOWN; do not infer it from the helper or scheduler. The raw archive is retained under .local/archives with the hash in terminal-seal.json.

Decision: preserve this evidence, analyze the collector/attribution boundary, and keep all GT06 gates frozen. No ID reuse, blind retry, partial-run merge, or gate change.
