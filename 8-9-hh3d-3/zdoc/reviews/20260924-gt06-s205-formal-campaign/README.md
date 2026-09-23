# GT06 S208 terminal package

`gt06-s205-formal-01` is sealed as a failed fresh formal attempt. It completed 14 batches and failed in batch 14 command processing with `TERMINAL_IDENTITY`. The final inspect lookup received a bounded `CONNECTION_LIMIT` rejection whose fallback response command id was `transport.request`, so the command identity guard rejected it.

Cleanup recorded the owner wrapper exit 1, import exit 0, closed/zero Job state and no retained owner handle. The editor target exit was not independently recorded; no natural exit is inferred. This package is diagnostic failure evidence only: it does not prove a leak, ownership, root cause, or GT06 acceptance.

The next repair must be limited to the proven transport/harness boundary, covered by focused tests, and dispatched under a fresh campaign id. Do not merge partial batches, retry this id, alter timeout/profile/baseline/counter/RSS gates, or use scheduler state as process proof.
