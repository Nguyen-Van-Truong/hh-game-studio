from pathlib import Path
import shutil

here = Path(__file__).resolve().parent
root = here.parents[2]
plan = root / 'zdoc/8-9-godot-blender-agent-studio-plan.txt'
archive = here / 'archive/tools-plan-s119.txt'
archive.parent.mkdir(exist_ok=True)
if not archive.exists():
    shutil.copyfile(plan, archive)
text = plan.read_text(encoding='utf8')
repls = [
    ('Revision S119', 'Revision S120'),
    ('IMPLEMENTATION=GT06_S119_LOOKUP_RECOVERY_RUNNING_S117_INTERRUPTED_S118_IMPORT_COMPLETE', 'IMPLEMENTATION=GT06_S120_FORMAL_RETRY_PREP_S119_LOOKUP_BOUNDARY_TERMINAL_S117_INTERRUPTED_S118_IMPORT_COMPLETE'),
    ('PLAN_REVISION=S119', 'PLAN_REVISION=S120'),
    ('GT06_EVIDENCE_STATUS=S116_FORMAL_FAILED_HOST_STATUS_GAP; S117_01_JOB_READBACK_FAILED_BEFORE_ENGINE; S117_02_IMPORT_WALL_LIMIT_ZERO_BATCHES; S118_IMPORT_VERBOSE_COMPLETED; S117_03_INTERRUPTED_WITHOUT_TERMINAL_RECORD; S119_DIAGNOSTIC_RUNNING; ZERO_ACCEPTED_FULL_RUNS', 'GT06_EVIDENCE_STATUS=S116_FORMAL_FAILED_HOST_STATUS_GAP; S117_01_JOB_READBACK_FAILED_BEFORE_ENGINE; S117_02_IMPORT_WALL_LIMIT_ZERO_BATCHES; S118_IMPORT_VERBOSE_COMPLETED; S117_03_INTERRUPTED_WITHOUT_TERMINAL_RECORD; S119_LOOKUP_BOUNDARY_FAILED_BATCH8; ZERO_ACCEPTED_FULL_RUNS'),
    ('GT06_ACTIVE_DIAGNOSTIC=gt06-s119-lookup-boundary-01_RUNNING_VIA_DEMAND_TASK; S117-03 interrupted after 3 batches without terminal record and sealed AUTHORITY0; S118 import-only completed11.359s/target656exit0; S117-01/02 terminal preserved', 'GT06_ACTIVE_DIAGNOSTIC=gt06-s119-lookup-boundary-01_TERMINAL_ORIGINAL_FAILURE_BATCH8_ADMISSION_UNKNOWN; S117-03 interrupted after 3 batches without terminal record and sealed AUTHORITY0; S118 import-only completed11.359s/target656exit0; S117-01/02 terminal preserved'),
    ('GT06_NEXT_ACTION=Observe gt06-s119-lookup-boundary-01 via demand-task receipt/live identity/shorttail then terminal timings/HTTP first failure/exits/Jobs/handles/pins/Stop. This is a fresh diagnostic only; original 11-batch boundary/max1230s and stock source/profile remain unchanged, no formal campaign.', 'GT06_NEXT_ACTION=Seal S119 raw and derived reader output, retain observed overlap as correlation-only, delete its demand task after terminal verification, then prepare one fresh formal GT06 campaign only with unchanged source/profile/workstation and original gates; no repair or threshold change.'),
    ('TIẾN ĐỘ HIỆN HÀNH — S119, ngày 19-09-2026', 'TIẾN ĐỘ HIỆN HÀNH — S120, ngày 19-09-2026'),
    ('S117-03 đã bị gián đoạn sau 3 batch, không có result/timing/target-exit nên không suy nguyên nhân; packet AUTHORITY=0 giữ 69 file và 41 loại trừ cục bộ. Probe launcher S119 không chạy engine đã exit thật 0, task instances=0. S119-01 tiếp tục lookup experiment bằng demand-only task, stock nonverbose import, fresh ID; giữ stage20s/15CPU/2GiB, 11 batch/original gates/max1230s và loại khỏi F13/F14.', 'S117-03 đã bị gián đoạn sau 3 batch, không có result/timing/target-exit nên không suy nguyên nhân; packet AUTHORITY=0 giữ 69 file và 41 loại trừ cục bộ. Probe launcher S119 không chạy engine đã exit thật 0, task instances=0. S119-01 đã terminal ở batch8 với 8 gate rows, ADMISSION_UNKNOWN, lookup timeout2006.271ms và max status gap5208.0547ms; Job zero/closed, handles released, source/execution unchanged, editor target exit UNKNOWN. Reader đã qua 3 negative tests và ghép được overlap với reload/snapshot_true/append/sqlite_commit; đây chỉ là tương quan quan sát, không phải root cause hay repair.'),
    ('S117-03 dispatch12:49:16Z, supervisor40172/host22976/editor42060; raw bị gián đoạn lúc batch3, không có terminal receipt. S119 probe đã chứng minh wrapper chờ và ghi exit thật; S119 diagnostic đang chạy, chỉ đọc terminal khi task kết thúc. Reader draft/next.md ở s118-import-boundary vẫn giữ giới hạn UNKNOWN.', 'S117-03 dispatch12:49:16Z, supervisor40172/host22976/editor42060; raw bị gián đoạn lúc batch3, không có terminal receipt. S119 probe chứng minh wrapper chờ và ghi exit thật. S119 diagnostic supervisor36240 exit1, target22720 exit1, import14052 exit0, editor target exit UNKNOWN; task instances0. Seal manifest2fc45bc6bf7ccad1a49d86993f5bc1386ac2738583dc05af6b1917f471293fae giữ120 raw/portable files và38 exclusions. No formal PASS.'),
    ('GT06_DIAGNOSTIC_EXCLUSION=All instrumented/static/supplemental and failed partial runs S70–S117 excluded from F13/F14.', 'GT06_DIAGNOSTIC_EXCLUSION=All instrumented/static/supplemental and failed partial runs S70–S119 excluded from F13/F14.'),
]
for old, new in repls:
    if text.count(old) != 1:
        raise SystemExit(f'PLAN_ANCHOR:{old[:50]}:{text.count(old)}')
    text = text.replace(old, new, 1)
plan.write_text(text, encoding='utf8', newline='')
print('PLAN_S120_UPDATED')
