"""Archive the prior tools-plan bytes and record terminal S100 honestly."""
from pathlib import Path
import hashlib
import json

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
PLAN = ROOT / 'zdoc/8-9-godot-blender-agent-studio-plan.txt'

before = PLAN.read_bytes()
archive = BASE / 'tools-plan-s100.txt'
with archive.open('xb') as stream:
    stream.write(before)
digest = hashlib.sha256(before).hexdigest()
with (BASE / 'plan-archive.json').open('x', encoding='utf-8') as stream:
    json.dump({'authority': 0, 'archived_revision': 'S100', 'file': archive.name,
               'sha256': digest, 'purpose': 'Historical progress, superseded by S101'}, stream, indent=2)
    stream.write('\n')
text = before.decode('utf-8')
updates = {
    'PLAN_REVISION': 'S101',
    'IMPLEMENTATION': 'GT06_S100_IMPORT_FAILURE_RETAINED_FOCUSED_DIAGNOSIS',
    'GT06_EVIDENCE_STATUS': 'S100_IMPORT_WALL_LIMIT_20S_ZERO_BATCHES_NO_ACCEPTANCE',
    'GT06_WORKING_SOURCE_STATUS': 'S97_SOURCE_UNCHANGED_S100_IMPORT_FAILURE_CLEANUP_VERIFIED',
    'GT06_BENCHMARK_CAMPAIGN': 'gt06-s100-campaign-01',
    'GT06_BENCHMARK_STATUS': 'TERMINAL_FAILED_IMPORT_20_203S_NO_ACTIVE_BENCHMARK',
    'GT06_ACTIVE_DIAGNOSTIC': 'NONE_LAUNCHED; PREPARING_SHORT_COPIED_HISTORY_AND_IMPORT_OBSERVERS',
    'GT06_FULL_CAMPAIGN': 'gt06-s100-campaign-01; LAUNCH1_FAILED_IMPORT; ZERO_BATCHES; FRESH_ID_REQUIRED_IF_SOURCE_CHANGES',
    'GT06_NEXT_ACTION': 'Measure a short copied-history HTTP probe and one owned cold import with startup telemetry; repair only a demonstrated cause or measured improvement. No blind full campaign retry, no unchanged 35-batch command-only rerun. Preserve all thresholds, Stop and failed attempts.',
}
lines = text.splitlines()
for index, line in enumerate(lines):
    key = line.split('=', 1)[0]
    if key in updates:
        lines[index] = key + '=' + updates[key]
text = '\n'.join(lines) + '\n'
text = text.replace('Revision S100 |', 'Revision S101 |', 1)
start = text.index('TIẾN ĐỘ HIỆN HÀNH — ')
end = text.index('Rà phạm vi claim S76:', start)
current = f'''TIẾN ĐỘ HIỆN HÀNH — S101, ngày 19-09-2026 (mốc run ghi UTC)
GT-01–05 ACCEPTED; GT-06 IN_PROGRESS; GT-07–10 chưa mở. Chưa có full benchmark
đủ 10 cặp. Source4293acf2d628, formal51closure và profile giữ nguyên ở marker.

S100 gt06-s100-campaign-01 launch1 FAILED ở import, trước batch0.
STAGE_WALL_LIMIT20s; elapsed20.203s (supervisor tổng63.984s không phải import
limit). Target54424 có startup receipt; stdout75bytes chỉ banner, stderr rỗng;
chỉ sinh .godot/.gdignore, chưa có filesystem scan milestone. Natural target
exit UNKNOWN, helper2; host7588 actualexit1. Hai Jobzero/closed/handles sạch,
parent ownedtreezero; schedulerstate3/result1/noinstances. Query00:44:06Z
không còn PID12452/7588/54424; không suy missing exit từ absence hoặc scheduler.
151exactcopies ở reviews/20260919-gt06-s100-recovery/failure, manifest
4b645aa18585f0878ac9ac868215c5bf3b9ba00b1043767a2dfe62ed32c64e51.
S97/S98 import cùng binary/20s limit chạy4.578/4.765s. S98 initial project
chỉ khác run_id. Chưa chứng minh lỗi code hoặc nguyên nhân môi trường S100.

Đang chuẩn bị ba lane độc lập (không critic): import startup observer giữ20s;
đo streaming hash trên bản sao journal; HTTP ngắn có attribution trên history
S98. Root tuần tự hóa mọi phép đo/engine. Không đổi runtime trước bằng chứng,
không chạy lại fullcampaign chỉ vì source vẫn giống hoặc một diagnostic xanh.

S99 command-only35batch COMPLETE4707.391s, maxgap1591.3252ms ởb25;
target33344/helper46072actual0/cleanup sạch. Batch0 khoảng38s lênb34 khoảng229s
theo history tăng. Supplemental-only, không Godot/ACK và không phase timing;
không giải thích lookup2s trong coupled run. Summary96714640aa7a4f4de326bbe62a02c83bf271768c9d72856da98b9872345d06c5
ở reviews/20260918-gt06-s99-command-residency. Không lặp78phút để chỉ nhận
một kết quả không tái hiện; probe tiếp phải đo đúng phase cần chẩn đoán.

S98 FAILED b17 sau18partialbatch: hostgap2043.7348ms, admitted.96 lookup
timeout2002.5627ms rồi READBACK_CONFIRMED; nativegap594.998ms/counters71128/6.
Cleanup sạch nhưng editor/supervisor naturalexit UNKNOWN. Attribution7b9f4f6fe4702c6bd9e2df6f1cb8f85dcef9fa29e01b9e0fa4956935b2ea3ca6;
terminal reconciliation1bad488b993dd3082ab8fb008a55f1e032cfccb7f9d59122559a9a71bba83dda.
Giữ raw, không ghép18partialrows vào F13/F14. Snapshot workstation hậu-terminal
không causal; original pagefile *_kb labels sai đơn vị (Win32_PageFileUsage MB),
committed_bytes_in_use null là unavailable. Đọc supplement errata, không dùng
chúng để quy lỗi thiếu RAM hoặc nới gate.

S97 coupled diagnostic35batch đã xong, allactualexit0/Jobsclean, counters71128/6,
maxnativegap756.589ms, HTTPzero transportfail/open span/identityloss/drop.
Không dataset nghiệm thu. S97 reader86affected+4binding+6overlay+24nativecases
đã kiểm; native6success0/18expected86, malformed collector repair chỉ derived
metadata. Reader packet821sharedfiles+3metadata/2727logicalrecords manifest
e377ecbff14bfb284f9ee70084138571c6f1f5959609e760622f7d2e1b70555c.
S96 ACKREAD/S93lookup2s/S86ObjectDB+2 và mọi failed evidence trước vẫn giữ;
không nói đã sửa mọi nguyên nhân. Các worker không thay final critics.

Đường còn lại: đủ10freshpairs×35batch,5warmup+30measured,1000HTTP+100native;
original gates, actual exits/trees/handles/hash/dataset. Reuse functional đúng
dependency (F01–F15 ở s83-mapping), freeze finalmanifest+requirement→evidence,
hai critic MỚI độc lập samehash PASS/TICK=yes rồi coordinator ACCEPT.
Sau đó GT07 concurrency/recovery →GT08CI/export/Android máy thật →GT09
conformance →GT10 install/upgrade/rollback. HHWorldS23/SuperagentSA2 riêng sauGT10.
Lịch duy nhất ti-p-t-c-hh3d-tools đã sửa bỏ S99 còn chạy; không hứa ETA toànplan.

Bài học: load_fixture trước campaign.source_files để lấy đủ51dependency;
48map khi module chưa import không phải source drift. Failure ở import là lane
khác lookup gap; sửa metadata từ raw khi đủ chứng cứ, không chạy lại engine vô ích.
Archive toàn planS100: reviews/20260919-gt06-s100-recovery/tools-plan-s100.txt,
AUTHORITY=0, SHA256={digest}.

'''
PLAN.write_text(text[:start] + current + text[end:], encoding='utf-8', newline='\n')
print(json.dumps({'revision': 'S101', 'archive_sha256': digest, 'runtime_changed': False}))
