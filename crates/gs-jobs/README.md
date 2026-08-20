# gs-jobs

Imagegen job state machine (MASTER 8.2 / T6.1). Pure functions + `Path`.
On-disk objects use `BTreeMap` so JSON keys stay ordered.

## Layout

```
.gs/jobs/queue/<job_id>.job.json
.gs/jobs/running/<job_id>.job.json   + lease {worker_id, heartbeat_at}
.gs/jobs/done/<job_id>.job.json      succeeded|failed|cancelled|timed_out
.gs/jobs/cancel/<job_id>.marker      pause/cancel
.gs/staging/jobs/<job_id>/{out.png,result.json}
.gs/staging/quarantine/<job_id>/     late results (not ingestible)
```

`job_id` **is** `command_id`. Retrying the same `command_id` does not create a
second queue file. There is no `commands.json` sidecar.

`dest_rel_hint` is an ingest hint only — never a write path.

Workers may write **only** `out.png` and `result.json` under
`.gs/staging/jobs/<job_id>/`. `assert_worker_path_allowed` rejects `assets/`
(GS-EC-55) using component checks plus `canonicalize` + prefix.

Job JSON never stores bus tokens or C API keys (I8).

## Claim on Windows (GS-EC-51)

`claim` is `std::fs::rename(queue/file → running/file)`. On Windows that is
`MoveFile` / `MoveFileEx` **without** replace: if the dest exists the call
fails; if another claimer already moved the source, the loser gets
file-not-found. Same-volume directory pair (`.gs/jobs/queue` →
`.gs/jobs/running`). Lease is written afterwards with tmp+rename (I6).

## Not in this crate

- `asset.gen_image` / `ingest_staged` / Jobs UI (M6-2)
- Real ComfyUI generation (worker may probe the URL; it does not claim success)
