"""Coordinator documentation changes, independent of worker source leases."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
Z=HERE.parents[1]
names=["8-9-godot-blender-agent-studio-plan.txt","8-9-hh-world-gameplay-viet-nam-plan.txt"]
for i,name in enumerate(names):
 p=Z/name
 s=p.read_text(encoding="utf-8")
 assert "PLAN_REVISION=S17" in s
 s=s.replace("| Revision S17 |","| Revision S18 |",1).replace("PLAN_REVISION=S17","PLAN_REVISION=S18",1)
 if i==0:
  s=s.replace("GT01_EVIDENCE_STATUS=DIAGNOSTIC_ONLY","GT01_EVIDENCE_STATUS=PARTIAL_RUNTIME_UNREVIEWED",1)
  s=s.replace("GT01_PENDING=PIN_PROVENANCE,BOOTSTRAP_SAFETY,HEADED_UI,PROCESS_TREE,BLENDER_FIXTURE,ROLLBACK,TWO_CRITICS","GT01_PENDING=BOOTSTRAP_HARDENING,TOOLCHAIN_REPRO,HEADED_UI,BLENDER_FIXTURE,ROLLBACK,TWO_CRITICS",1)
  s=s.replace('Quyết định pin S17 (theo lựa chọn owner "Godot stock 4.7.2"):',"Quyết định pin S17 (coordinator chọn trong quyền triển khai owner đã cấp):",1)
  s=s.replace("ghi version, full commit từ --version, SHA256/SHA512, license MIT, platform,","ghi version và abbreviated commit từ --version; đối chiếu full commit từ tag\nsource official godotengine/godot (không lấy commit của repo godot-builds).\nGhi SHA256/SHA512, license MIT, platform,",1)
  anchor="9 GT còn PLANNED;"
  progress="""S18 (10-09, tiếp tục GT-01): đã chạy Godot 4.7.2 stock trên snapshot riêng,
import + parse trace + input headless + QUITTING có host exit và Job Object.
ZIP editor và export templates đã khớp SHA256/SHA512-SUMS official. Đây là
PARTIAL_RUNTIME_UNREVIEWED, không là nghiệm thu GT-01. Runner còn hardening
path/version/source-copy/negative tests; toolchain cần launcher tái tạo, headed
UI, Blender readback và rollback cùng hai critic chưa đủ. Các audit Grok r6
có finding sai thực tế nên phải phân xử trước sửa; không đồng nhất exit0 với
kết quả worker hợp lệ. Checkpoint WIP và review hiện hành:
./reviews/20260910-r6/REVIEW-RESULT.md
Godot làm trước trong plan công cụ; H2 tiếp tục đợi GT-10. Không đổi DoD hoặc
tự nhận plan hoàn hảo từ static PASS.
"""
 else:
  anchor="32 H2 PLANNED;"
  progress="""S18 (10-09) đồng bộ tiến độ tools: GT-01 có bằng chứng headless 4.7.2
chưa nghiệm thu. Game vẫn chưa triển khai và đợi GT-10; không thay LEGAL-VN,
EX/Q, release profile hay capacity gates. Review hiện hành:
./reviews/20260910-r6/REVIEW-RESULT.md
"""
 assert anchor in s
 s=s.replace(anchor,progress+anchor,1)
 p.write_text(s,encoding="utf-8",newline="\n")

# Keep the S17 validator/evidence immutable. S18 inherits every structural
# check and changes only the explicitly documented progress status.
prev=HERE.parent/"20260910-r5"
v=(prev/"validate_plans.py").read_text(encoding="utf-8")
v=v.replace("Static S17 plan checks.","Static S18 plan checks.")
v=v.replace("GT01_EVIDENCE_STATUS=DIAGNOSTIC_ONLY","GT01_EVIDENCE_STATUS=PARTIAL_RUNTIME_UNREVIEWED")
v=v.replace("S16 GT01 diagnostic status and missing evidence are explicit","S18 GT01 partial status and missing evidence are explicit")
v=v.replace('default="freeze-s17.json"','default="freeze-s18.json"').replace('default="static-s17.json"','default="static-s18.json"').replace('default="S17"','default="S18"')
(HERE/"validate_plans.py").write_text(v,encoding="utf-8",newline="\n")
t=(prev/"test_review_s17.py").read_text(encoding="utf-8").replace("S17Tests","S18Tests").replace("'revision': 'S17'","'revision': 'S18'").replace("'selfcheck-s17.json'","'selfcheck-s18.json'").replace("GT01_EVIDENCE_STATUS=DIAGNOSTIC_ONLY","GT01_EVIDENCE_STATUS=PARTIAL_RUNTIME_UNREVIEWED").replace("'diagnostic status'","'partial status'")
(HERE/"test_review_s18.py").write_text(t,encoding="utf-8",newline="\n")
print("S18 documentation ready; run freeze and tests after report exists.")
