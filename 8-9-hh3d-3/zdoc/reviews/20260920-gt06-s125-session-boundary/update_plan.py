"""Shorten current progress, preserving the exact historical plan archive."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
plan = ROOT / 'zdoc/8-9-godot-blender-agent-studio-plan.txt'
archived = (HERE / 'archive/s124-plan.snapshot').read_bytes()
assert plan.read_text(encoding='utf-8').splitlines() == archived.decode('utf-8').splitlines(), \
    'Plan content changed; reconcile before writing'
source = json.loads((HERE / 'source-manifest.json').read_bytes())
text = archived.decode('utf-8').replace('Ngày 19-09-2026, Asia/Saigon | Revision S124',
                                     'Ngày 20-09-2026, Asia/Saigon | Revision S125')
updates = {
 'IMPLEMENTATION': 'GT06_S125_SESSION_REVALIDATION_FIXED_RETAINED_COUNTER_UNRESOLVED',
 'PLAN_REVISION': 'S125',
 'GT06_EVIDENCE_STATUS': 'ZERO_ACCEPTED_FULL_RUNS; S116_FORMAL_FAILED; S123_RETAINED_COUNTER_FAILED; S124_SEVEN_BATCH_DIAGNOSTIC_COMPLETED; S125_AUTH_RACE_REPRODUCED_AND_REPAIRED',
 'GT06_WORKING_SOURCE_STATUS': 'S125_CANDIDATE_TRANSPORT53_AND_BENCHMARK166_TESTS_PASS; NOT_FORMAL',
 'GT06_CURRENT_SOURCE_CLOSURE': source['source_closure'],
 'GT06_SOURCE_CHECKPOINT': 'S125_PENDING_CHECKPOINT; PREVIOUS_RUNTIME=c4ae9cb2',
 'GT06_ACTIVE_DIAGNOSTIC': 'NONE; NO_ENGINE_RUNNING_AT_S125_CHECK',
 'GT06_NEXT_ACTION': 'Freeze S125 candidate and prepare one full35 diagnostic with post-failure-only handle observation, stock native/host workload and natural completion; do not repeat the seven-batch prefix. This distinguishes later counter recurrence and removes host timing wrappers. No diagnostic dataset; preserve original gates and all failures.',
}
lines = []
for line in text.splitlines():
    key = line.split('=', 1)[0]
    if key in updates:
        line = key + '=' + updates[key]
    if key in ('GT06_S122_S123_S124_BOUNDARY_STATUS', 'GT06_S109_DIFFERENTIAL_REVIEW',
               'GT06_S111_STATIC_ATTRIBUTION', 'GT06_S112_VERIFIED_PATH_ATTRIBUTION'):
        continue
    if key == 'GT06_DIAGNOSTIC_EXCLUSION':
        line = 'GT06_DIAGNOSTIC_EXCLUSION=All failed partial/instrumented/supplemental runs through S125 excluded from F13/F14; preserve their raw, missing-evidence gaps and lessons. History in S124 archive and referenced review packets.'
    lines.append(line)
text = '\n'.join(lines) + '\n'
start = text.index('TIẾN ĐỘ HIỆN HÀNH — S124')
end = text.index('Rà phạm vi claim S76:', start)
current = '''TIẾN ĐỘ HIỆN HÀNH — S125, ngày 20-09-2026 (timestamps UTC)
GT01–05 ACCEPTED; GT06 IN_PROGRESS; GT07–10 chưa mở; zero accepted full runs.
S125 tái hiện bốn trường hợp lease/Stop chờ host lock rồi session bị rotate/hết
hạn nhưng vẫn được nhận. Sửa hẹp: check_current lại ngay sau khi lấy host lock;
lookup read-only vẫn trả pending từ snapshot sau durable admission. Before có
4 failure; after 4 test methods pass; transport/recovery 53/53, benchmark166/166
exit0. Đây không sửa hay chứng minh nguyên nhân editor handles/latency.
Evidence: reviews/20260920-gt06-s125-session-boundary/. Profile/native giữ nguyên.
Core transport thay đổi nên không chuyển chữ ký GT02/GT05 cũ sang candidate;
functional lane nào có dependency khác phải chứng minh lại trước final closure.

S116 formal thất bại status gap2041.7971ms. S123 candidate đạt batch0–4 rồi
trượt handles555→560 ở batch5; S124 cùng source chạy0–6, handles trở về555 tại
4–6, không trượt. Hai lượt đều diagnostic, native stock; S124 có instrumentation
phía host. Không kết luận leak/no-leak/root cause hoặc nới gate từ bộ đếm này.
Mọi failure S70–S124 và khoảng trống exit/cleanup cũ được giữ nguyên.

Bước tiếp theo: một diagnostic đủ35 batch, bỏ wrapper timing journal/SQLite,
chỉ chụp handle sau khi original gate đã báo lỗi; nếu hoàn tất thì đi qua normal
exit của stock child. Câu hỏi mới: counter có tái tăng sau prefix và các handle
đó giảm hay giữ sau rejection? Không chạy lại prefix7 chỉ để tìm may mắn PASS.
Nếu không tái hiện, kết quả chỉ là full diagnostic, không biến thành formal.
GT06 formal vẫn10freshpairs×35batch (5warmup+30measured), fulldataset/exits/
Jobs/handles/source hashes/allattempts, hai critic độc lập cùng finalclosure.
GT07→GT10 tuần tự; GT08 cần Android thật. Chưa có ETA đáng tin cho toànplan.

Plan S124 trước tinh gọn được lưu byteexact/AUTHORITY0 tại
reviews/20260920-gt06-s125-session-boundary/archive/s124-plan.snapshot.
Hash và nguồn của archive nằm trong manifest.json cùng thư mục. Không xóa raw.
Bài học: kiểm authorization sau thời gian chờ khóa; kiểm transport base class
và subclass recorder riêng; giữ raw stdout rỗng/trailing whitespace và hash,
không sửa logfile để làm sạch Git diff; phân biệt native stock với host overlay.

'''
text = text[:start] + current + text[end:]
plan.write_text(text, encoding='utf-8', newline='\n')
print(json.dumps({'archive_sha256': hashlib.sha256(archived).hexdigest(),
                  'new_lines': len(text.splitlines()), 'old_lines': len(archived.splitlines())}))
