# GT-06 formal06 — terminal closeout, 2026-09-29

`AUTHORITY=0`; GT-06 remains `IN_PROGRESS` with **zero accepted pairs**.
Formal06 is a terminal **PRODUCT_FAIL**, not an infrastructure abort and not a
partial pass. The first pair completed four warmup batches. Pair two did not
start.

The host campaign exited with code 1 after batch 4 failed `TERMINAL_TIMEOUT` on
the final inspect command. The command stayed `ACCEPTED_PENDING` beyond the
existing five-second terminal budget; its final recorded terminal latency was
5344.2655 ms. The highest completed-prefix status gap was 541.7268 ms, below
the 2000 ms gate, but the pair is still failed because the required command
did not reach a verified terminal result. The source, profile, counters and
prefix captures therefore cannot form a dataset or acceptance evidence.

The supervisor returned code 1. Host wrapper exit was 1, editor helper exit
was 2 during cleanup, import observer exit was 0, and the editor target's
natural exit was not recorded. Both owned Jobs closed with zero active members,
no retained handles and no cleanup error. No watchdog stop latch was written.
The CPU sample stream reached 100%, but its longest consecutive over-95%
interval was about 31 seconds, below O4.1's 60-second watchdog rule; the
classification must remain PRODUCT_FAIL. RAM minimum was 2.0659 GiB and commit
maximum 67.15%. These observations are diagnostic and do not change O1/O4 or
the five-second terminal budget.

The measured source remained frozen at
`d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475` (54 files)
with profile
`9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e`.
Raw evidence is preserved under `studio/.local/reviews/gt06-o4-formal-06/` and
the immutable closeout is:

- manifest: `studio/.local/reviews/gt06-formal06-closeout-20260929/manifest.json`
  (SHA-256 `14c0196e1e78f05baf8bea6ac381853f3a52de2ad768cd4a277cfe10fbd07144`)
- raw ZIP: `studio/.local/reviews/gt06-formal06-closeout-20260929/raw.zip`
  (SHA-256 `e22163326124ecf65e0b71ace9e0d4963f52357e8671a7062bf3b19bb1dd404c`)

Do not resume or relabel this run. Before a new ID, review the terminal-timeout
boundary and schedule a fresh O4.1 preflight with stable CPU; a new run must
use the same unchanged acceptance thresholds and a newly verified source
closure. The daily INFRA_ABORT count for 2026-09-29 remains 0/2 because this
was a product failure. O2 static work may continue separately; GT-07 remains
closed until GT-06 is accepted.
