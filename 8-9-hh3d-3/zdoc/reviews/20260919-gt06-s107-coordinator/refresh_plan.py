"""Archive exact previous progress and replace only the current status block."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[3]
plan = root / "zdoc/8-9-godot-blender-agent-studio-plan.txt"
raw = plan.read_bytes()
archive = Path(__file__).parent / "archive"
archive.mkdir(exist_ok=True)
with (archive / "tools-plan-S106-prefix-in-progress.txt").open("xb") as out:
    out.write(raw)
with (archive / "manifest.json").open("x", encoding="utf-8", newline="\n") as out:
    json.dump({"AUTHORITY": 0, "historical_only": True,
               "file": "tools-plan-S106-prefix-in-progress.txt", "size_bytes": len(raw),
               "sha256": hashlib.sha256(raw).hexdigest()}, out, indent=2)
    out.write("\n")
text = raw.decode("utf-8")
newline = "\r\n" if "\r\n" in text else "\n"
text = text.replace("\r\n", "\n")
replacements = {
    "Revision S106": "Revision S107",
    "PLAN_REVISION=S106": "PLAN_REVISION=S107",
    "IMPLEMENTATION=GT06_S105_TERMINAL_PACKET_AND_S106_STATIC_COLLECTOR_REPAIR":
        "IMPLEMENTATION=GT06_S106_PREFIX_NON_REPRODUCED_AND_S107_PREVIEW_COST_DIAGNOSTIC_PREPARATION",
    "GT06_EVIDENCE_STATUS=S102_FORMAL_FAILED; S103_HANDLE_EXCURSION; S104_DERIVED_READER; S105_BOUNDARY_COMPLETE_ATTRIBUTION_INCOMPLETE; NO_ACCEPTED_BENCHMARK_SAMPLE":
        "GT06_EVIDENCE_STATUS=S102_FORMAL_FAILED; S106_PREFIX_NON_REPRODUCED; S107_PREPARATION_ONLY; ZERO_ACCEPTED_FULL_RUNS",
    "GT06_ACTIVE_DIAGNOSTIC=gt06-s106-handles-prefix-01; DISPATCHED_20260919T054103Z; CHECK_FRESH_LIVENESS":
        "GT06_ACTIVE_DIAGNOSTIC=NONE; S106_PREFIX_TERMINAL_20260919T055012Z; S107_NOT_LAUNCHED",
    "GT06_NEXT_ACTION=One fresh S106 six-batch two-snapshot prefix after verified preflight; keep runtime/profile/helper fixed. No identical-prefix retry or formal retry without proven narrow repair. Preserve all raw; use source-backed latency research only for a separate justified experiment.":
        "GT06_NEXT_ACTION=Validate generated-only S107 ABBA40 native preview-cost diagnostic and one owned bounded run; preserve full formal save coverage. No repeated identical prefix or formal retry without proven narrow repair.",
    "GT06_DIAGNOSTIC_EXCLUSION=All instrumented diagnostics and failed/partial prefixes S70-S106 are excluded from F13/F14; no PASS/no-leak/root-cause inference.":
        "GT06_DIAGNOSTIC_EXCLUSION=All instrumented diagnostics and failed/partial prefixes S70-S107 are excluded from F13/F14; no PASS/no-leak/root-cause inference.",
}
for old, new in replacements.items():
    if text.count(old) != 1:
        raise RuntimeError("S107_PLAN_ANCHOR " + old)
    text = text.replace(old, new)
start = text.index("TIẾN ĐỘ HIỆN HÀNH — S106,")
end = text.index("Rà phạm vi claim S76:", start)
current = """TIẾN ĐỘ HIỆN HÀNH — S107, ngày 19-09-2026 (run timestamps UTC)
GT01–05 ACCEPTED; GT06 IN_PROGRESS; GT07–10 chưa mở. Chưa có full benchmark PASS.
S106 prefix01 đã kết thúc05:50:12Z, không còn engine chạy khi kiểm06:00:40Z.
Đủ6batch0–5,6000HTTP+600native; planned S106_PREFIX_BOUNDARY, không lỗi mới.
Hai PSS gắn đúng gate/sample: editor563→555 (-8), Event118→114, Thread47→44,
IoCompletion12→11;192unavailable mỗi snapshot. Count không là object identity.
ObjectDB71128/resources6 ổn định; HTTPmax905.7962ms/native714.183ms, transport0.
PSS4/5:8.4505/10.0524ms, targetbefore/after khớp, observer204, allreleased/errors0.
Kết luận NON_REPRODUCED; đóng nhánh lặp identicalprefix, không no-leak/repair.
Outer22376actual0; host46864actual1/helper1 do boundary; import53260actual0/helper0;
editor23356naturalUNKNOWN/helper2. Recorded Jobs/probes/threads sạch. Import native
wrapper-close UNKNOWN; outermanagedDispose không thay nativeCloseBOOL; chưa liveStop.
Raw studio/.local/reviews/gt06-s106-handles-prefix-01 và sibling -outer giữ nguyên.
Packet reviews/20260919-gt06-s106-prefix-result/:95exactcopies,84refs/60unique,
manifest53cd7e5c44e13ca8febda965aa8d70f6294ead96985b7f536a70446862a2ee0d.

S107 đang chuẩn bị, CHƯA dispatch: một editor diagnostic40cycles,10nhóm ABBA,
A=stock save_scene(), B=save_scene_as(SCENE,false), hard180s; không HTTP/PSS.
Generated-only overlay exactbase13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95;
runtime53/profile giữ S102. Không sửa formal save path hay bịa B returnError=0:
B trả void và ghi null; signal/file/script/semantic undo+reload mới chứng minh hiệu lực.
Giữ tất cả40rows và outliers; firstA serialization normalization được ghi rõ,
các bytes scene sau save/reload phải khớp, script nguồn không đổi. Ghi callentry/
return/signal/phase+frame/nextdispatch; originalheartbeat/deadline không chuyển.
Nativehelper, runner+ownedcleanup, packetaudit chia ba Astraultra; root giữ reader/
observer/plan. Static+integration trước engine; một writer/file. Không finalcritic.
Đọc reviews/20260919-gt06-s106-latency-next.md và s107-preview-cost/README.md.
Stock preview có viewport readback/PNG/progressUI; source-backed mechanism, chưa
chứng minh nguyên nhân S102. Production publication dùng ResourceSaver/staging,
khác stock benchmark save. Không đổi workload nghiệm thu theo kết quả vi đo này.
Nếu phép so sánh không phân biệt được hoặc thiếu boundary, đóng nhánh với
NO_DISCRIMINATING_RESULT/UNKNOWN; không tự tăng số vòng hoặc retry cùng phép đo.

S102 nativegap2109.351ms b6/c74 SAVE→SAVE_WAIT vẫn unresolved; host1936.8697ms,
HTTPfailure0 là boundary riêng. scene_saved không phải callreturn. S103 handle
555→561 chưa chứng minh leak. S104 đọc lại100/600rows trên raw đúng frameorder;
Engine processframe có thể tăng trong synchronous save. S105 collector failures
và packet264copies/manifestc08d33e4bd99678a29ff28fcf0ffed2135c0e70c1155198d1aba7b514622cbe4
giữ nguyên. S106 sửa collector,30static và actual1batch preflight; packet50copies
manifest383c832ae411d1b31596a1228152b0a6608bc81e665b1097f99a077812d0c7e0.
Giữ failure S70–S106; collector lỗi thì sửa derivedmetadata trên raw đủ bằng chứng,
không rerun engine vô ích; snapshot chưa ghi không thể tạo hồi tố. No Stop bypass.

Không đổi heartbeat/timeout/counter/RSSbaseline, subtractoverhead, trim/pinRAM,
priority hoặc process khác. Không engine/test/hash audit nặng cạnh phép đo.
Nghiệm thu giữ10freshpairs×35batch (5warmup+30measured),1000HTTP+100native/batch,
7410s/run; dataset/hash/actualtarget+helperexits/ownedtree/Jobs/handles/Stop/allattempts.
Reusefunctional chỉ exactdependency. ĐủDoD mới freezefinalmanifest+requirement→test→
evidence, hai critic MỚI cùnghash PASS/TICK=yes, coordinatorACCEPT rồi GT07→GT10.
GT08 cần Androidmáythật. HH World/Superagent riêng sauGT10; tools không là game.
Lịch duy nhất ti-p-t-c-hh3d-tools theo trạng thái mới; máy/app cần hoạt động.
Chưa ETA toànplan/không hứa xong trước sáng. S106progress exactarchive/hash/AUTHORITY0
ở reviews/20260919-gt06-s107-coordinator/archive/; lịch sử cũ tiếp tục giữ nguyên.

"""
text = text[:start] + current + text[end:]
plan.write_bytes(text.replace("\n", newline).encode("utf-8"))
print(json.dumps({"archived_sha256": hashlib.sha256(raw).hexdigest(),
                  "new_sha256": hashlib.sha256(plan.read_bytes()).hexdigest()}))
