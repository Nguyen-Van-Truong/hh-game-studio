# S110 admission-timeout failure

This packet preserves the terminal S110 stock campaign failure. It is diagnostic evidence only and is excluded from GT06 acceptance.

- Campaign: `gt06-s110-formal-01`
- Run: `gt06-s110-formal-01.r00.a01`
- Result: `ADMISSION_UNKNOWN` at batch 5, command `inspect.455`
- Transport: `/v1/commands` `getresponse` timeout, 2085.5802 ms
- Completed: batches 0–4 only; no accepted full run
- Source/profile/workstation were unchanged; all raw bytes remain under `failure/raw` and `failure/supervisor`.
- Host and editor jobs/handles were closed; editor target exit is explicitly UNKNOWN.

The timeout is not converted to PASS, leak, root-cause, or an engine failure. The next action is attribution before any fresh campaign.
