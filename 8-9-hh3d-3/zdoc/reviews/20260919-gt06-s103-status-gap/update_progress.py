"""One-time S102 history archive and S103 progress correction; no runtime edits."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
PLAN = HERE.parent.parent / '8-9-godot-blender-agent-studio-plan.txt'
raw = PLAN.read_bytes()
text = raw.decode('utf-8')
assert 'PLAN_REVISION=S102' in text
archive = HERE / 'tools-plan-s102.txt'
with archive.open('xb') as stream:
    stream.write(raw)
digest = hashlib.sha256(raw).hexdigest()
(HERE / 'tools-plan-s102-authority.json').write_text(json.dumps({
    'authority': 0, 'file': archive.name, 'sha256': digest,
    'reason': 'Historical S102 snapshot; current plan supersedes running-state claims.'
}, indent=2) + '\n', encoding='utf-8')
updates = {
    'IMPLEMENTATION': 'GT06_S103_NATIVE_STATUS_GAP_DIAGNOSIS_PREPARATION_NO_ENGINE_RUNNING',
    'PLAN_REVISION': 'S103',
    'GT06_EVIDENCE_STATUS': 'S102_FAILED_NATIVE_STATUS_GAP_BATCH6_NO_FULL_RUN; S103_DIAGNOSTIC_PREPARATION',
    'GT06_WORKING_SOURCE_STATUS': 'S102_FROZEN_53_RUNTIME_FILES_UNCHANGED; NO_ACTIVE_FORMAL_CAMPAIGN',
    'GT06_BENCHMARK_STATUS': 'FAILED_20260919T011926Z_NATIVE_GAP2109.351MS; TASK_RETIRED_012534Z',
    'GT06_ACTIVE_DIAGNOSTIC': 'NONE; S103_SAVE_BOUNDARY_PREFIX_HELPERS_IN_PREPARATION',
    'GT06_FULL_CAMPAIGN': 'gt06-s102-campaign-01; LAUNCH1_FAILED; ZERO_FULL_RUNS; SOURCE53_UNCHANGED',
    'GT06_NEXT_ACTION': 'Review/freeze S103 additive save-boundary helper; run owned one-batch preflight, then one bounded seven-batch diagnostic prefix if valid. Preserve original gates/source/profile; no blind campaign retry.',
}
lines = text.splitlines()
for index, line in enumerate(lines):
    if line.startswith('Ngày 19-09-2026, Asia/Saigon | Revision S102'):
        lines[index] = line.replace('Revision S102', 'Revision S103')
    for key, value in updates.items():
        if line.startswith(key + '='):
            lines[index] = key + '=' + value
text = '\n'.join(lines) + '\n'
start = text.index('TIẾN ĐỘ HIỆN HÀNH — S102')
end = text.index('Rà phạm vi claim S76:', start)
section = f'''TIẾN ĐỘ HIỆN HÀNH — S103, ngày 19-09-2026 (mốc run ghi UTC)
GT01–05 ACCEPTED; GT06 IN_PROGRESS; GT07–10 chưa mở. Chưa có full run PASS.
Runtime giữ source checkpoint56bfd448 và53file closure
7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467;
profile0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85.

S102 gt06-s102-campaign-01 launch1 đã FAILED lúc01:19:26Z, elapsed705.906s,
batch6/joint_observation. Có7 captured batches0–6, không fullrun/accepted sample.
Lỗi CAMPAIGN_STATUS_GAP là NATIVE2109.351ms; HTTP max1936.8697ms dưới2000ms,
transport failures0/first_failure=null. Không được gọi lỗi này là HTTP lookup.
Native cycle74 SAVE→SAVE_WAIT cách2109.351ms; raw save2129.219ms. scene_saved
signal sau906.724ms, heartbeat sau signal1202.398ms. Thiếu save_scene RETURN
timestamp nên chưa tách synchronous call với thời gian chờ engine/frame.
Batch6 nhiều phase cùng chậm; memory/scheduling pressure chỉ là giả thuyết.
ObjectDB71128/resources6 ổn định, editorhandles561→555, RSS giảm; không leak claim.

Host actual32404exit1/helper1; editor naturalexit UNKNOWN/helper29916exit2,
Jobszero/closed, handles/probes/threads released theo terminal cleanup. Import
10368actual0/helper0, observerclosed/error0. Import Python wrapper handle close
chưa có record tường minh; không suy leak hay claim toàn bộ handles đã chứng minh.
Supervisor actualexit UNKNOWN; returned_exit1/scheduler1 không thay actualexit.
30 fixed Stop slots vắng. Schedulerstate3/result1/noinstances đã lưu; task retired
01:25:34Z. PID32404 được tái dùng bởi chrome.exe01:21:58Z, không điều khiển PID cũ.
Hiện không engine/benchmark chạy; không retry S102 tự động.

Failure packet ở reviews/20260919-gt06-s103-status-gap/failure:
259raw exact copies,221portable,38local excluded journals/commandstore/cache.
Manifest28a1f859a062001f0624de01a791e231864a46b92a1bfa4e06c4435b5abfef38.
53source bytes đã khớp; raw và portable là hai hash domains riêng. Giữ failure
immutable, scheduler retirement là supplement ngoài packet. Chi tiết: batch-summary,
code-cause-review, http-attribution và cleanup-review; các review này không critic.

Ba Astra ultra worker đang làm helper độc lập: overlay native, owned prefix harness,
và bộ đọc boundary. Không sửa formalruntime. Overlay exact-basehash, chỉ instrument
generated plugin: call entry/return, scene_saved, save frame và process kế tiếp.
Bounded records; original heartbeat/deadline/gate/workload giữ nguyên. Hiện CHƯA launch.
Sau static review: một owned preflight1000HTTP+100native, rồi một diagnostic7batch
0–6 tối đa1200s nếu preflight đủ. Dừng ở original failure hoặc ranh giới prefix;
forced diagnostic stop không native exit0, không F13/F14, không benchmark PASS.
Complete boundary records vẫn phân tích được khi termination sau đó là diagnostic;
record thiếu boundary là UNKNOWN, lifecycle claim giữ riêng. Không đánh heartbeat
trong scene_saved để che thời gian chậm. Không đổi journal để chữa native gap.

S102130/130affectedtests và owned short preflight đã giữ nguyên; observability
HTTP8192events/64active/import100ms256samples tính đầy đủ overhead trong time/RSS.
Chưa chứng minh sửa latency2s/startup20s. S100shortprobes/S97reader24cases/
S99command35batch là supplemental. Giữ toàn bộ failuresS70–S102, không trộn prefix.

Đường nghiệm thu không đổi:10freshpairs×35batch (5warmup+30measured), mỗi batch
1000HTTP+100native,7410s/run. Reuse functional chỉ exact dependency; verify dataset,
hashes, sidecars, target/helperexits, ownedtree, Jobs/handles, allattempts và Stop.
Collector lỗi sau engine xong: sửa derived metadata từ raw đủ bằng chứng.
ĐủDoD mới freeze finalmanifest+requirement→evidence, hai critic MỚI độc lập cùng
hash PASS/TICK=yes rồi coordinatorACCEPT. Sau đó GT07→GT10 tuần tự, GT08 Android
máy thật hardgate; HH World/Superagent riêng sauGT10. Chưa ETA toàn plan.

Lịch duy nhất ti-p-t-c-hh3d-tools phải theo S103; không lặp trạng thái RUNNING cũ.
Giữ máy/app hoạt động. Không hứa xong trước sáng. Archive S102 byteexact/AUTHORITY0:
reviews/20260919-gt06-s103-status-gap/tools-plan-s102.txt,
SHA256={digest}.

'''
text = text[:start] + section + text[end:]
PLAN.write_bytes(text.replace('\n', '\r\n').encode('utf-8'))
print(json.dumps({'archived_sha256': digest, 'revision': 'S103'}))
