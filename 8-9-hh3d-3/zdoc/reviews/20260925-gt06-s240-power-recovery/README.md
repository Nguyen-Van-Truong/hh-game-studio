# S240 â€” power-recovery audit

Status: `AUTHORITY=0`, diagnostic only. This packet records the recovery audit
after the workstation rebooted repeatedly on 2026-09-24. It does not change the
GT06 acceptance gate and does not convert the interrupted campaign into a
failure or a pass.

## Findings

- `gt06-s239-formal-01` was dispatched at `2026-09-24T07:44:41.5687841Z`
  (`14:44:41.5687841` Asia/Saigon). Its raw directory was last written at
  `07:44:54.683460Z`. The host was waiting in batch `0` ready (not a retained ready receipt); no
  measured batch was captured.
- Event 41 was recorded at `14:46:19.992` local time, about 98 seconds after
  dispatch. This timestamp overlap is consistent with an interruption but
  does not prove which event caused it. No Godot, Blender, CDB, or WinDbg
  process remains after reboot.
- The raw S239 source closure is intact: 53/53 files are present and their
  SHA-256 values match `source-files.json`; the campaign and attempt context
  agree on source closure `d7c78724ed827c8182af62c3f7bc1489d8dd35d29abe1f70216736a896e66bb3`.
- The S239 attempt is therefore `POWER_INTERRUPTED_PARTIAL`, with
  `formal_acceptance=false`. It cannot resume its old PID and must not be
  merged into a future formal campaign.
- System logs contain 21 Event 41 records on 2026-09-24 and one more at
  04:06:42 on 2026-09-25. Event 41 is a generic unexpected-restart record;
  all 22 had `BugcheckCode=0` and `WHEABootErrorCount=0`, but several include
  sleep/power-button state and are not proof of 22 identical hard power cuts.
- Event 46 (`volmgr`) at `17:43:55.900` says crash-dump initialization failed.
  There were no WHEA, disk, StorAHCI, StorNVMe, or NTFS events in the queried
  interval. These absences do not prove that the PSU, motherboard, storage, or
  thermals are healthy.
- A current read-only inventory reports a Gigabyte B560M AORUS PRO AX board,
  BIOS F9, i5-10400F, and GTX 1660 Ti. Because the board/PSU were replaced,
  the pre-outage formal workstation profile is not automatically reusable.

The 22 Event 6008 records report previous shutdown dates of September 24; the
last was logged on September 25. The 14:46 boot record reports 14:14:20 as the
previous shutdown time, inconsistent with the later durable S239 timestamps.
Keep both raw observations; do not claim an exact power-loss time from them.

Git full object validation exited 0 (dangling history retained). S235 and S236
verifiers rechecked their raw/ZIP bytes; S238 catalog verification passed.
The current source plus both S239 frozen copies each match 53 declared hashes;
28 raw JSON documents parse, and the SQLite index passes read-only integrity
check. S239 raw and supervisor were sealed as 169 files / 170 ZIP members.
The old demand-only task was retired only after archive readback verification.
No old host/editor exit, Job closure, or handle-release receipt is invented.
These checks do not re-audit every historical GT01-GT05 artifact.

## Required handling

Keep S239 raw evidence and all earlier Authority-0 failures. Record the
interruption and seal metadata before any new run. Before a fresh formal ID,
capture a new non-secret hardware/workstation profile, verify the pinned source
and benchmark profile, and run the existing readiness checks. Do not alter the
10 fresh pairs Ã— 35 batches gate, timeout, counter, RSS, or baseline. A fresh
campaign is required; same-run continuation or scheduler result `0` is not
accepted evidence.

## Limits

This packet does not identify whether the old PSU, old motherboard, or another
power-path component caused the outage. Event 41 and missing WHEA records cannot
make that attribution. See Microsoft's [Event ID 41 guidance](https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/event-id-41-restart).
