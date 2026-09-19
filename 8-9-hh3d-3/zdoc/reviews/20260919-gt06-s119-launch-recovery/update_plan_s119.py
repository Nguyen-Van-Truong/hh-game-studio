from pathlib import Path

plan = Path(__file__).resolve().parents[3] / 'zdoc/8-9-godot-blender-agent-studio-plan.txt'
data = plan.read_bytes()
replacements = [
    (b'Asia/Saigon | Revision S118 |', b'Asia/Saigon | Revision S119 |'),
    (b'IMPLEMENTATION=GT06_S117_LOOKUP_03_RUNNING_S118_IMPORT_COMPLETE', b'IMPLEMENTATION=GT06_S119_LOOKUP_RECOVERY_RUNNING_S117_INTERRUPTED_S118_IMPORT_COMPLETE'),
    (b'PLAN_REVISION=S118', b'PLAN_REVISION=S119'),
    (b'GT06_EVIDENCE_STATUS=S116_FORMAL_FAILED_HOST_STATUS_GAP; S117_01_JOB_READBACK_FAILED_BEFORE_ENGINE; S117_02_IMPORT_WALL_LIMIT_ZERO_BATCHES; S118_IMPORT_VERBOSE_COMPLETED; S117_03_DIAGNOSTIC_RUNNING; ZERO_ACCEPTED_FULL_RUNS', b'GT06_EVIDENCE_STATUS=S116_FORMAL_FAILED_HOST_STATUS_GAP; S117_01_JOB_READBACK_FAILED_BEFORE_ENGINE; S117_02_IMPORT_WALL_LIMIT_ZERO_BATCHES; S118_IMPORT_VERBOSE_COMPLETED; S117_03_INTERRUPTED_WITHOUT_TERMINAL_RECORD; S119_DIAGNOSTIC_RUNNING; ZERO_ACCEPTED_FULL_RUNS'),
    (b'GT06_ACTIVE_DIAGNOSTIC=gt06-s117-lookup-boundary-03_RUNNING_OBSERVED; S118 import-only completed11.359s/target656exit0; S117-01/02 terminal preserved', b'GT06_ACTIVE_DIAGNOSTIC=gt06-s119-lookup-boundary-01_RUNNING_VIA_DEMAND_TASK; S117-03 interrupted after 3 batches without terminal record and sealed AUTHORITY0; S118 import-only completed11.359s/target656exit0; S117-01/02 terminal preserved'),
    (b'GT06_NEXT_ACTION=Observe gt06-s117-lookup-boundary-03 via launch-03 receipts/live identity/shorttail then terminaltimings/HTTPfirstfailure/exits/Jobs/handles/pins/Stop. This resumes unexecuted lookup experiment with fresh ID and stocknonverbose import after S118import success; original11batch boundary/max1230s, no formalcampaign.', b'GT06_NEXT_ACTION=Observe gt06-s119-lookup-boundary-01 via demand-task receipt/live identity/shorttail then terminal timings/HTTP first failure/exits/Jobs/handles/pins/Stop. This is a fresh diagnostic only; original 11-batch boundary/max1230s and stock source/profile remain unchanged, no formal campaign.'),
    ('TIẾN ĐỘ HIỆN HÀNH — S118, ngày 19-09-2026'.encode(), 'TIẾN ĐỘ HIỆN HÀNH — S119, ngày 19-09-2026'.encode()),
    ('S117-03 tiếp tục lookup experiment chưa có batch, stocknonverbose import/freshID.\r\nGiữ stage20s/15CPU/2GiB và originalprojectrecipe;11batch/originalgates/max1230s.'.encode(), 'S117-03 đã bị gián đoạn sau 3 batch, không có result/timing/target-exit nên không suy nguyên nhân; packet AUTHORITY=0 giữ 69 file và 41 loại trừ cục bộ. Probe launcher S119 không chạy engine đã exit thật 0, task instances=0. S119-01 tiếp tục lookup experiment bằng demand-only task, stock nonverbose import, fresh ID; giữ stage20s/15CPU/2GiB, 11 batch/original gates/max1230s và loại khỏi F13/F14.'.encode()),
    ('S117-03 dispatch12:49:16Z, supervisor40172/host22976/editor42060; query mới trước\r\nkết luận. Readerdraft và next.md ở s118-import-boundary chờ terminal mới kiểm.'.encode(), 'S117-03 dispatch12:49:16Z, supervisor40172/host22976/editor42060; raw bị gián đoạn lúc batch3, không có terminal receipt. S119 probe đã chứng minh wrapper chờ và ghi exit thật; S119 diagnostic đang chạy, chỉ đọc terminal khi task kết thúc. Reader draft/next.md ở s118-import-boundary vẫn giữ giới hạn UNKNOWN.'.encode()),
]
for old, new in replacements:
    count = data.count(old)
    if count != 1:
        raise SystemExit(f'PLAN_ANCHOR_COUNT:{old[:50]!r}:{count}')
    data = data.replace(old, new, 1)
plan.write_bytes(data)
print('PLAN_S119_UPDATED')
