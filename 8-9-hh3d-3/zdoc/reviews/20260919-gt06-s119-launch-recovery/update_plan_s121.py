"""Advance the tools plan from S120 to the verified S121 offline closure."""
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / 'zdoc/8-9-godot-blender-agent-studio-plan.txt'
ARCHIVE = Path(__file__).resolve().parent / 'archive'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'EXPECTED_ONCE:{old[:80]}:{text.count(old)}')
    return text.replace(old, new, 1)


def main():
    raw = PLAN.read_bytes()
    old_hash = sha256(raw).hexdigest()
    ARCHIVE.mkdir(exist_ok=True)
    old = ARCHIVE / 'tools-plan-s120.txt'
    if not old.exists():
        old.write_bytes(raw)
    text = raw.decode('utf-8')
    text = replace_once(text, 'Revision S120', 'Revision S121')
    text = replace_once(text, 'IMPLEMENTATION=GT06_S120_FORMAL_RETRY_PREP_S119_LOOKUP_BOUNDARY_TERMINAL_S117_INTERRUPTED_S118_IMPORT_COMPLETE',
        'IMPLEMENTATION=GT06_S121_OFFLINE_BOUNDARY_REVIEW_S119_READER_V2_PORTABLE_SEAL_V2')
    text = replace_once(text, 'PLAN_REVISION=S120', 'PLAN_REVISION=S121')
    text = replace_once(text,
        'GT06_NEXT_ACTION=Seal S119 raw and derived reader output, retain observed overlap as correlation-only, delete its demand task after terminal verification, then prepare one fresh formal GT06 campaign only with unchanged source/profile/workstation and original gates; no repair or threshold change.',
        'GT06_NEXT_ACTION=Keep formal retry closed. Retain S119 raw, corrected offline reader v2 and portable seal v2; use the exact lifecycle boundary only to design a narrow, reviewable repair. Do not change source/profile/workstation, timeout, gates, baseline, priority or RSS policy; run a new bounded diagnostic only after a static repair decision identifies a distinguishing check.')
    text = replace_once(text,
        'S119-01 đã terminal ở batch8 với 8 gate rows, ADMISSION_UNKNOWN, lookup timeout2006.271ms và max status gap5208.0547ms; Job zero/closed, handles released, source/execution unchanged, editor target exit UNKNOWN. Reader đã qua 3 negative tests và ghép được overlap với reload/snapshot_true/append/sqlite_commit; đây chỉ là tương quan quan sát, không phải root cause hay repair.',
        'S119-01 terminal ở batch8 với 8 gate rows, ADMISSION_UNKNOWN, lookup timeout2006.271ms và max status gap5208.0547ms; Job zero/closed, handles released, source/execution unchanged, editor target exit UNKNOWN và import-wrapper CloseHandle UNKNOWN. Reader v2 qua 5 offline controls, ràng buộc lifecycle đầy đủ, containment theo thời gian, port pair, PID và source/profile; báo boundary dispatch của lookup và bốn timing span còn giữ. Đây vẫn chỉ là tương quan/suy luận tĩnh, chưa phải root cause, repair hay acceptance.')
    text = replace_once(text,
        'Seal manifest2fc45bc6bf7ccad1a49d86993f5bc1386ac2738583dc05af6b1917f471293fae giữ120 raw/portable files và38 exclusions. No formal PASS.',
        'Original seal manifest2fc45bc6bf7ccad1a49d86993f5bc1386ac2738583dc05af6b1917f471293fae được giữ như metadata dẫn xuất lịch sử. Portable seal v2 đã sửa ở zdoc/reviews/20260919-gt06-s119-launch-recovery/s119-seal-v2/ với external manifest hash a62b29c4340ad9fd116e0f64c585fb922ed4c6f47de5bdfe1cb851366b199784; file copy được kiểm byte và cache local bị loại vẫn được liệt kê. No formal PASS.')
    text = replace_once(text, 'TIẾN ĐỘ HIỆN HÀNH — S120, ngày 19-09-2026 (timestamps UTC)',
        'TIẾN ĐỘ HIỆN HÀNH — S121, ngày 19-09-2026 (timestamps UTC)')
    text += ('\nS121 static boundary note: transport._dispatch holds the host lock before lookup; '
             'S119 retained server.dispatch had not entered server.lookup when the client lookup timed out, '
             'while host.finish held its journal guard through reload/snapshot and append. This is a pinned-code '
             'and lifecycle boundary, not proof of disk, OS, scheduler or leak cause. Keep formal GT06 retry closed '
             'until a narrow repair and distinguishing bounded diagnostic are reviewed.\n')
    PLAN.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))
    print({'from_sha256': old_hash, 'to_sha256': sha256(PLAN.read_bytes()).hexdigest(), 'archive': str(old)})


if __name__ == '__main__':
    main()
