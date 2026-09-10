"""Static S18 plan checks. These do not prove semantic/runtime/legal acceptance.

S17 (independent coordinator audit, 2026-09-10): both plans carry PLAN_DESIGN_CRITICS stating that
no design critic verdict has been ACCEPT from S6 to S16; the tools plan pins Godot 4.7.2-stable
official (4.7.1 diagnostic only), forbids absolute host paths in lock/evidence, requires the GT-01
runner to parse the GT01_TRACE line and owned process tree instead of exit 0 alone, adds machine
checks for worker output and an escalation rule after two rejected batches, and requires a WIP
checkpoint commit or a recorded reason for IN_PROGRESS source. Every S6-S16 check is retained.
"""
from pathlib import Path
from collections import Counter
import argparse, datetime, hashlib, json, math, re, sys

OUT = Path(__file__).resolve().parent
Z = OUT.parents[1]
NAMES = ["8-9-godot-blender-agent-studio-plan.txt", "8-9-hh-world-gameplay-viet-nam-plan.txt"]
EXPECTED = [[f"GT-{i:02}" for i in range(1,11)],
            [f"H2-P{p}-{i:02}" for p,n in enumerate([3,3,4,4,4,3,3,3,3,2]) for i in range(1,n+1)]]
EX_COUNT = 53
CLIENT_WPS = ["H2-P2-01","H2-P2-02","H2-P2-03","H2-P2-04","H2-P4-01","H2-P4-02","H2-P4-03","H2-P4-04","H2-P5-01","H2-P5-02"]

def validate(manifest, inputs, root):
    errors, warnings, stats, graph, specs = [], [], [], {}, {}
    def check(ok, message):
        if not ok: errors.append(message)
    check(set(inputs)==set(NAMES), "exactly two active source inputs")
    rows_manifest = manifest.get("files", [])
    check(len(rows_manifest)==2 and {r["path"] for r in rows_manifest}==set(NAMES), "manifest file set")
    by_name = {r["path"]:r for r in rows_manifest}
    aggregate = hashlib.sha256("\n".join(sorted(f"{r['path']} {r['sha256']}" for r in rows_manifest)).encode()).hexdigest()
    check(aggregate==manifest.get("manifest_sha256"), "aggregate manifest digest")
    revision = manifest.get("revision")
    texts = {}
    for index, name in enumerate(NAMES):
        raw = inputs[name]
        try: s = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            errors.append(name+": invalid UTF-8"); continue
        texts[name] = s
        sha = hashlib.sha256(raw).hexdigest()
        check(by_name.get(name,{}).get("sha256")==sha, name+": source hash")
        check(by_name.get(name,{}).get("bytes")==len(raw), name+": byte count")
        check(not any(c in s for c in ["\r","\x00","\ufffd","\ufeff"]), name+": LF/control/BOM")
        check(not re.search(r"(?m)^(?:<{7}|={7}|>{7}|\+)",s), name+": conflict/patch residue")
        for key,value in {"PLAN_REVISION":revision, "EXECUTION_AUTHORIZATION":"OWNER_APPROVED_GATED",
                          "IMPLEMENTATION":("GT01_IN_PROGRESS" if index==0 else "NOT_STARTED"), "RUNTIME_ACCEPTANCE":"NONE",
                          "HUMAN_ACCEPTANCE":"NONE"}.items():
            check(re.findall(rf"(?m)^{key}=(.+)$",s)==[value], name+": "+key)
        check(f"| Revision {revision} |" in s, name+": title revision")
        check(not re.search(r"\[[xX]\]",s), name+": unexpected completed checkbox")
        kind = ["TOOLS","GAME"][index]
        sentinel = f"END_OF_{kind}_PLAN"
        check(s.count(sentinel)==1 and bool(re.search(rf"{sentinel}\nDATE=\d{{4}}-\d{{2}}-\d{{2}} Asia/Saigon\n\Z",s)), name+": terminal sentinel/date")
        top=[int(m.group(1)) for m in re.finditer(r"(?m)^(\d)\. (.+)$",s) if m.group(2).isupper()]
        check(top==list(range(10)), name+f": top-level sections {top}")
        table=list(re.finditer(r"(?m)^(\d{2}) \| ([A-Z0-9-]+) \| ([^|\n]+) \| ([^|\n]+) \| ([A-Z_]+)$",s))
        ids=[m.group(2) for m in table]
        check(ids==EXPECTED[index], name+": ordered WP rows")
        check([int(m.group(1)) for m in table]==list(range(1,len(EXPECTED[index])+1)), name+": row ordinals")
        check([m.group(5) for m in table] == (["IN_PROGRESS"]+["PLANNED"]*9 if index==0 else ["PLANNED"]*32), name+": table status for S17 freeze")
        check(re.findall(r"(?m)^PLAN_DESIGN_CRITICS=(.+)$",s)==["NO_ACCEPTED_VERDICT_S6_TO_S16"], name+": PLAN_DESIGN_CRITICS header states no accepted design verdict")
        check(re.findall(r"(?m)^CURRENT_VALID_WP=(.+)$",s)==[EXPECTED[index][0]], name+": current WP")
        for m in table:
            wp=m.group(2)
            check(wp not in graph, "duplicate WP "+wp)
            graph[wp]=[d.strip() for d in m.group(4).split(",")]
        headings=list(re.finditer(r"(?m)^### ((?:GT-\d{2}|H2-P\d-\d{2})) — .+$",s))
        check([m.group(1) for m in headings]==EXPECTED[index], name+": row/spec bijection and order")
        for i,m in enumerate(headings):
            end=headings[i+1].start() if i+1<len(headings) else s.index(["4. TQ —","6. EX —"][index],m.end())
            block=s[m.end():end]; wp=m.group(1); specs[wp]=block
            for label in ("ALLOWED","BUILD","VERIFY","DoD"):
                check(bool(re.search(rf"(?m)^{label}:",block)), wp+": missing "+label)
        prefix,count=[("TX",18),("EX",EX_COUNT)][index]
        ex=list(re.finditer(rf"(?m)^{prefix}(\d{{2}}) — (.+)$",s))
        check([int(m.group(1)) for m in ex]==list(range(1,count+1)), name+": exception sequence")
        all_ids=set(EXPECTED[0]+EXPECTED[1])
        for m in ex:
            owners=re.findall(r"GT-\d{2}|(?:H2-)?P\d-\d{2}",m.group(2))
            owners=[o if o.startswith(("GT-","H2-")) else "H2-"+o for o in owners]
            check(bool(owners) and all(o in all_ids for o in owners), prefix+m.group(1)+": valid owning WPs")
        for relative in re.findall(r"(?m)^\./([^\n]+)$",s):
            p=(root/relative).resolve()
            check(p.is_relative_to(root.resolve()) and p.exists(), name+": broken local link "+relative)
        gate_pattern = r"(?m)^TQ(\d{2}):" if index==0 else r"(?m)^## Q(\d{2}) —"
        check([int(v) for v in re.findall(gate_pattern,s)]==list(range(9 if index==0 else 7)), name+": quality gate sequence")
        paragraphs=Counter(re.sub(r"\s+"," ",p).strip() for p in s.split("\n\n") if len(p)>190)
        for p,n in paragraphs.items():
            if n>1: warnings.append(name+f": repeated long paragraph x{n}: "+p[:100])
        if index==1: check(not re.search(r"\bST-?\d{2}\b",s), name+": stale active ST routing")
        stats.append({"path":name,"sha256":sha,"bytes":len(raw),"lines":len(s.splitlines()),
                      "wp_rows":len(ids),"specs":len(headings),"exceptions":len(ex)})
    check(len(graph)==42, "42 unique WPs")
    external=[]; cross=[]
    for wp,deps in graph.items():
        for d in deps:
            if d not in graph: external.append((wp,d))
            if wp.startswith("GT-") and d.startswith("H2-"): errors.append("tool depends on game: "+wp+" -> "+d)
            if wp.startswith("H2-") and d.startswith("GT-"): cross.append((wp,d))
    check(external==[("GT-01","OWNER_START")], "only OWNER_START external dependency")
    check(cross==[("H2-P0-01","GT-10")], "single tools-to-game handoff")
    visited,active,order=set(),set(),[]
    def visit(wp):
        if wp in active: errors.append("DAG cycle at "+wp); return
        if wp in visited:return
        active.add(wp)
        for d in graph[wp]:
            if d in graph:visit(d)
        active.remove(wp);visited.add(wp);order.append(wp)
    for wp in graph:visit(wp)
    # Known closure regressions from independent S4 review.
    for wp,slice_id in {"H2-P1-02":"Q04-L0","H2-P3-03":"Q04-L1","H2-P4-01":"Q04-L2","H2-P4-04":"Q04-L3"}.items():
        check(slice_id in specs.get(wp,""), wp+": explicit network slice")
        check(not re.search(r"\bQ04-L(?![0-3])",specs.get(wp,"")), wp+": unsliced early network gate")
    check("EX44-A" in specs.get("H2-P2-03","") and not re.search(r"\bEX44(?!-A)",specs.get("H2-P2-03","")),
          "Solo EX44 closure cannot silently include online lifecycle")
    check("TQ08-B" in specs.get("GT-08","") and "TQ08-I" in specs.get("GT-10",""), "producer/installer gate split")
    # S6 closure checks: legal/scale/social/UX additions must have owner WPs and named gates.
    g=texts.get(NAMES[1],""); t=texts.get(NAMES[0],"")
    check(bool(re.search(r"(?m)^LEGAL-VN — ",g)) and all(f"  L{i} " in g for i in range(1,9)), "LEGAL-VN L1-L8 block present in 3.5")
    check("SCALE-LOCKS" in g and all(f"  SL{i} " in g for i in range(1,13)), "SCALE-LOCKS SL1-SL12 present in 3.2.1")
    check("**Q01-T (trend," in g and "Q01-T" in specs.get("H2-P0-02",""), "Q01-T trend gate defined and locked at P0-02")
    check("Q01-T" in g.split("## Q01 —")[0].split("## Q00 —")[-1], "Q00 requires Q01-T record for client WPs")
    for wp,needle in {"H2-P0-03":"i18n","H2-P3-01":"SCALE-LOCKS","H2-P3-02":"EX47","H2-P4-01":"EX45",
                      "H2-P4-02":"P2P_TRADE","H2-P4-04":"EX48","H2-P5-02":"EX50","H2-P6-01":"EX46",
                      "H2-P6-02":"LEGAL-VN","H2-P8-03":"LEGAL-VN","H2-P9-01":"LEGAL-VN"}.items():
        check(needle in specs.get(wp,""), wp+": missing S6 closure reference "+needle)
    check("EX46" in specs.get("H2-P4-01",""), "H2-P4-01: placement/AFK owner reference")
    check("P2P_TRADE" in g.split("## P03 —")[1].split("## P04 —")[0], "P03 shop row states P2P_TRADE default off")
    check(not re.search(r"(?m)^EX08 — .*\n(?:.*\n){0,3}.*Race buyer A/B \+ owner unpublish;",g), "EX08 no longer assumes P2P escrow by default")
    check("Naming/taxonomy convention" in specs.get("GT-05",""), "GT-05: naming convention deliverable")
    check("Perf collector" in specs.get("GT-06",""), "GT-06: perf collector schema shared with game Q01")
    # S7 closure checks: encode both S6 critic findings so a regression to S6 wording fails.
    p402=specs.get("H2-P4-02","")
    contract_402=p402.split("ALLOWED:")[0]
    check("REJECTED" in contract_402 and "KHÔNG thuộc closure" in contract_402 and "debit buyer + mint" in contract_402,
          "P4-02 CONTRACT is catalog debit+mint with transfer REJECTED and escrow outside closure")
    check("hoa hồng" not in p402.split("BUILD:")[1].split("VERIFY:")[0] or "không stock bán/giá riêng/escrow/hoa hồng" in p402,
          "P4-02 BUILD forbids stall stock/commission")
    check("giao dịch vật phẩm ảo" not in g.split("CURRENT_VALID_WP=")[0], "table row 16 no longer says durable virtual-item trading")
    check("trade phức tạp" not in g and "Virtual shop → item game" not in g, "no leftover P2P/marketplace-mint wording")
    check("không bao giờ mint item_instance" in g.split("## G05 —")[1].split("## G06 —")[0], "G05 MarketplaceDirectory never mints")
    check("Chủ quầy không nhận currency/điểm/hoa hồng" in g, "P04 stall owner receives no commission/points")
    check("phải bằng 0 khi P2P_TRADE off" in g, "A06 reconciliation: cross-account ownership transfers == 0")
    check("delete-vs-trade" not in g and "delete-vs-in-flight catalog purchase regression" not in specs.get("H2-P3-04","")
          and "do WP này sở hữu" in specs.get("H2-P4-02","").split("ALLOWED:")[0], "delete-vs-in-flight purchase fence owned only by P4-02")
    id_block=g.split("- ID contract")[1].split("- Epoch gameplay")[0]
    check("P0-02" in id_block and "UUIDv7" in id_block and "100k" in id_block,
          "shared ID contract locked before P2; P3 only consumes and measures")
    sl=g.split("SCALE-LOCKS — ")[1].split("Không nằm trong khóa")[0]
    for i in range(1,13):
        line=re.search(rf"(?m)^  SL{i} .+$",sl).group(0)
        check(bool(re.search(r"P\d-\d{2}",line)), f"SL{i} names at least one WP owner")
    check("SL12" in specs.get("H2-P3-01","") and "SL12" in specs.get("H2-P6-01",""), "SL12 owned by P3-01 schema and P6-01 measurement")
    check("SL6" in specs.get("H2-P3-01","") and "SL7" in specs.get("H2-P3-01","") and "SL7" in specs.get("H2-P2-03",""), "SL6/SL7 locked at P3-01 and P2-03 save schema_version")
    q00=g.split("## Q01 —")[0].split("## Q00 —")[-1]
    check("`Q01-T-<WP>`" in q00 and "report-only" in q00 and "không tự là fail CANDIDATE" in q00, "Q00: Q01-T record mandatory, values report-only")
    for wp in CLIENT_WPS:
        check(f"Q01-T-{wp[3:]}" in specs.get(wp,""), wp+": missing Q01-T-<WP> record reference")
    check("perf-collector.schema.json" in g.split("## Q01 —")[1].split("## Q02 —")[0], "game Q01 consumes GT-10 perf collector schema file")
    check("perf-collector.schema.json" in specs.get("GT-06","") and "perf-collector.schema.json" in t.split("TQ06:")[1].split("TQ07:")[0],
          "tools GT-06 and TQ06 name the same perf collector schema file")
    check("không phải catalog/economy SKU của game" in specs.get("GT-05","") and "quy tắc ID catalog" not in t, "GT-05 naming is fixture asset_id pattern, not game SKU")
    check("naming convention v1" in t.split("Hero contract:")[1].split("GLB không tự chuyển")[0] and "naming convention v1" in t.split("TQ05:")[1].split("TQ06:")[0],
          "tools 2.4 and TQ05 defer to naming convention v1")
    check("EX13-B" in g.split("EX13 — ")[1].split("EX14 — ")[0] and "EX13-B" in specs.get("H2-P4-01",""), "EX13-B leader succession owned by P4-01")
    check("Mất kết nối hủy bộ đếm AFK" in g and "không có AFK-trong-hold" in g, "EX46/P04: disconnect cancels AFK, hold uses EX12 TTL only")
    check("chủ không có nhà" in g.split("## P04 —")[1].split("## P05 —")[0] and "chủ không có nhà" in specs.get("H2-P4-01",""), "visit-when-away state owned by P4-01")
    check("Spawn pool có occupancy" in g.split("EX15 — ")[1].split("EX16 — ")[0] and "32 join đồng thời" in specs.get("H2-P3-03",""), "spawn scatter owned by P3-03/EX15")

    for ex,owner in {"EX51":"H2-P3-02","EX52":"H2-P3-03","EX53":"H2-P5-02"}.items():
        check(ex in specs.get(owner,"") and ex in specs.get("H2-P6-01",""), f"{ex} referenced by owner {owner} and P6-01")
    check("MarketplaceDirectory không mint" in specs.get("H2-P7-03",""), "P7-03 adapter no-mint statement")
    # S8 closure checks: residuals from the two S7 critics. Wrapped lines are compared whitespace-normalised;
    # VERIFY blocks are cut at the line-start label so the CONTRACT/VERIFY header is not mistaken for it.
    n=lambda s: re.sub(r"\s+"," ",s)
    verify_of=lambda wp: n(re.split(r"(?m)^VERIFY:",specs.get(wp,""),maxsplit=1)[-1]) if re.search(r"(?m)^VERIFY:",specs.get(wp,"")) else ""
    check("không gồm P3-*" in q00 and "P2-01→H2-P5-02" not in q00 and not any(f"Q01-T-P3-0{i}" in g for i in range(1,5)),
          "Q00 Q01-T applies to the ten client WPs only, never P3-*")
    check("quota mua/account/ngày" in contract_402 and "vượt quota/ngày" in p402 and "P4-02" in g.split("EX52 — ")[1].split("EX53 — ")[0]
          and "P4-02" in re.search(r"(?m)^EX52 — .+$",g).group(0), "EX52 catalog daily purchase quota owned by P4-02 CONTRACT/VERIFY")
    check("kill switch đăng ký mới" in specs.get("H2-P6-02","") and "CS rebind" in specs.get("H2-P6-02",""), "P6-02 owns EX51 kill switch and CS rebind runbook")
    check("mất cả máy lẫn mã khôi phục" in re.sub(r"\s+", " ", g.split("EX51 — ")[1].split("EX52 — ")[0]).lower() and "Mất cả máy và mã khôi phục" in specs.get("H2-P3-02",""),
          "EX51 dual-loss CS path stated in EX51 and P3-02")
    check("60 phút" in g.split("EX52 — ")[1].split("EX53 — ")[0] and "24 h chỉ ở P9-02" in n(specs.get("H2-P6-01","")), "EX52 bot soak 60 min at P6-01, 24h only P9-02")
    check("SL3" in specs.get("H2-P6-01","") and "SL6" in specs.get("H2-P8-03",""), "SL3/SL6 measured in P6-01/P8-03 VERIFY")
    check("inventory/escrow/listing" not in g and "escrow/listing chỉ là bảng dự phòng fixture" in g, "v0.1 writer list has no escrow/listing")
    check("studio/contracts/perf-collector.schema.json" in g.split("## Q01 —")[1].split("## Q02 —")[0], "game Q01 uses the packaged schema path")
    ex13=g.split("EX13 — ")[1].split("EX14 — ")[0]
    check("active_set rỗng → party kết thúc ngay" in ex13 and "không party sống mà không leader" in ex13 and "active_set rỗng" in specs.get("H2-P4-01","")
          and "hết hold thì party kết thúc" not in g, "EX13-B single CAS: empty active set ends party immediately; no leaderless live party")
    check("chủ không có nhà" in verify_of("H2-P4-01"), "P4-01 VERIFY includes visit-when-away state")
    check("mint/sink theo ngày khớp journal" in verify_of("H2-P3-04"), "P3-04 VERIFY covers mint/sink telemetry")
    check("theo số P0-02" in verify_of("H2-P4-01") and "30 s/actor TTL 10 s" not in verify_of("H2-P4-01"), "P4-01 VERIFY uses P0-02 numbers instead of hardcoded TTLs")
    # S9: targeted regressions from coordinator audit F01-F08.
    def between(s, a, b):
        if a not in s or b not in s.split(a,1)[-1]:
            check(False, "missing section: "+a); return ""
        return n(s.split(a,1)[1].split(b,1)[0])
    p04=between(g,"## P04 —","## P05 —")
    l1=between(g,"  L1 ","  L2 ")
    l8=between(g,"  L8 ","i18n từ P0-03:")
    ex51=between(g,"EX51 —","EX52 —")
    p002=n(specs.get("H2-P0-02","")); p302=n(specs.get("H2-P3-02",""))
    check("SOLO_AFTER_CAP" not in g and "solo_release_eligible" in p04 and
          "unknown" in p04 and "BLOCKED" in p04 and "guest/offline/phiên Solo đã mở" in p04,
          "F01 Solo release scope must be enforceable; no runtime flag exemption")
    check("G4" in g and "NĐ116/2026" in g and "tester ngoài" in g and
          "legal-applicability.md" in p002 and "P3-01/P3-02" in p04,
          "F01 applicability/amendments before production consumer and external pilot")
    check(all(x in l1 for x in ["principal", "verified_contact", "guardian_link", "player_id", "không unique player", "key_version"])
          and "guardian + hai trẻ" in p302.lower() and "child token chọn adult" in p302,
          "F02 contact/player separation with guardian family and child authorization cases")
    check("OTP chỉ chứng minh kiểm soát contact" in ex51 and "không auto-link/merge" in ex51 and
          "không dùng ngưỡng vắng 90 ngày" in ex51 and "factor có trước độc lập" in ex51,
          "F03 OTP/contact cannot take over old principal; recent SIM risk included")
    check(all(x in ex51 for x in ["CAS recovery_revision", "revoke old sessions/refresh/room tickets/recovery tokens", "hai operator độc lập", "thiếu chứng cứ thì deny", "CS rate"]),
          "F03 recovery atomicity, revocation, CS proof and rate ownership")
    check("6 tháng" in l8 and "tháng lịch" in l8 and "service_end" in l8 and
          "30 ngày" in l8 and "restricted store" in l8 and "review_due" in l8 and "deletion replay" in l8,
          "F04 legal retention separated from anti-farm with hold/purge/restore")
    for wp,path in {"GT-05":"studio/contracts/naming-convention-v1.md", "GT-06":"studio/contracts/perf-collector.schema.json"}.items():
        allowed=between(specs.get(wp,""),"ALLOWED:","BUILD:")
        check(path in allowed, "F06 explicit producer ALLOWED: "+path)
    check("GT-10" in specs.get("GT-06","") and "manifest closure" in specs.get("GT-06",""),
          "F06 export manifest includes shared contract files")
    for lock in ["SL1","SL6"]:
        line=re.search(rf"(?m)^  {lock} .+$",g)
        check(bool(line and "P0-02" in line.group(0) and "P3-01 consume" in line.group(0)), "F07 early lock "+lock)
    check("identity-content-v1.json" in p002 and "security-profile.json" in p302 and
          "OTP/SMS" in p002 and "P3-02 khóa" in p002 and "AFK/idle/invite" not in g,
          "F08 shared schema early, single security numeric owner")
    check("khi hold leader hết hạn, active nhận leader" in specs.get("H2-P4-01",""),
          "F08 succession timing in WP verification")
    check("mọi finding S6 đã đóng" not in g and "EXECUTION_AUTHORIZATION=OWNER_APPROVED_GATED" in g,
          "Owner authorization is recorded independently of historical critic verdicts")
    # S12/S16 closure checks: typed release, load and deployment contracts are explicit.
    p002_raw=specs.get("H2-P0-02","")
    p601=specs.get("H2-P6-01","")
    p602=specs.get("H2-P6-02","")
    check(all(x in p002_raw for x in ["release-profile-v1", "solo_release_eligible", "decision_signature", "BLOCKED_RELEASE_PROFILE_SCHEMA", "source_manifest_sha256"]),
          "S16 release profile is closed-schema and provenance-bound")
    check("H2-P3-04" in specs.get("H2-P4-02","") and "H2-P5-03 ACCEPTED" in p601,
          "S16 economy and load dependencies are explicit")
    check(all(x in p601 for x in ["contracts/load-profile-v1.json", "1.000", "1.5x", "2.0x", "completed samples"]) and "coordinated omission" in g,
          "S16 load profile freezes workload, overload and sample rules")
    check(all(x in p602 for x in ["contracts/deployment-profile-v1.json", "fault-domain", "RPO/RTO", "BLOCKED_DEPLOYMENT_PROFILE"]),
          "S16 deployment profile binds environment, ownership and fail-closed rules")
    check("materialize/copy dưới fixture staged root" in t and "UNSUPPORTED_SAFE_OPEN_WINDOWS" in t,
          "S16 tool plan closes linked inputs and safe-open unsupported behavior")
    check("1000 mock commands" in t and "30 mẫu" in t and "p95" in t,
          "S16 tool benchmark fixes cardinality and measurements")
    policy="MODEL=grok-4.6; REASONING_EFFORT=xhigh; CLI=official_grok; FAST_FLAG=ONLY_IF_VERIFIED; NO_CODEX_WORKER/NO_CURSOR/NO_FALLBACK/NO_HIDDEN_SUBAGENTS"
    check(all(x.count(policy)==1 and "--no-subagents" in x for x in (t,g)),
          "S16 active plans require exact official Grok policy")
    check("DISPATCHABLE=NO_UNTIL_GT10_ACCEPTED" in g, "S16 game waits GT10")
    check("H2-P3-04" in graph.get("H2-P4-02",[]) and "H2-P5-03" in graph.get("H2-P6-01",[]),
          "S16 dependency table agrees with economy/load specs")
    check(all("EXECUTION_AUTHORIZATION=PLAN_ONLY" not in x for x in (t,g)),
          "S16 no stale active authorization")
    check(all(x in p002_raw for x in ["decision_signature.signature", "decision_signature.signed_payload_sha256", "manifest INPUT", "Trust registry độc lập", "JCS/RFC8785"]),
          "S16 acyclic signed payload and independent signer trust")
    check("GT01_EVIDENCE_STATUS=PARTIAL_RUNTIME_UNREVIEWED" in t and "GT01_PENDING=" in t,
          "S18 GT01 partial status and missing evidence are explicit")
    # S17 closure checks: pin decision, portable lock/evidence, runner acceptance, worker machine checks.
    gt01=specs.get("GT-01",""); gt01_build=between(gt01,"BUILD:","VERIFY:"); gt01_verify=verify_of("GT-01")
    pin=between(t,"Quyết định pin S17","GT-01/08 chứng minh")
    check("GT01_PIN_DECISION=GODOT_4.7.2_STABLE_OFFICIAL" in t and "4.7.2-stable standard" in pin and "SHA512-SUMS" in pin
          and "không được đưa vào package candidate GT-01" in pin and "S18 https://github.com/godotengine/godot-builds/releases/tag/4.7.2-stable" in t,
          "S17 pin decision: Godot 4.7.2-stable official with SUMS verification; 4.7.1 diagnostic only")
    check("không chứa đường dẫn tuyệt đối" in gt01_build and "toolchain.local.json" in gt01_build
          and "không chứa đường dẫn tuyệt đối/username" in n(between(t,"TQ01:","TQ02:")),
          "S17 lock is portable: no absolute host paths or usernames; host locations live in ignored local file")
    check(all(x in gt01_verify for x in ["GT01_TRACE", "Exit 0 đơn lẻ không là PASS", "UNVERIFIED_PROCESS_TREE không được xuất hiện", "--check-only"]),
          "S17 GT-01 runner acceptance parses the trace line, process tree and parse check; exit 0 alone is not PASS")
    check("KILL_ON_JOB_CLOSE" in n(between(t,"TX05 —","TX06 —")) and "GT-01" in re.search(r"(?m)^TX05 — .+$",t).group(0),
          "S17 TX05 names the owned-process-tree mechanism and includes GT-01")
    check("hai batch liên tiếp bị REJECT" in n(t) and "py_compile" in t and "coordinator tự viết deliverable" in n(t),
          "S17 worker outputs get machine checks and a bounded escalation rule")
    check("đường dẫn tuyệt đối host/username phải redact" in n(t) and "checkpoint commit" in n(t),
          "S17 committed evidence is path-redacted and IN_PROGRESS source has a checkpoint or a recorded reason")
    # Recompute concrete illustrative arithmetic; no deployment capacity proof.
    calculated={"rooms_cpu":math.floor(2400/(6*30)), "rooms_ram":math.floor(10/.6),
                "rooms_down":math.floor(87.5e6/(32*30e3)), "rooms_up":math.floor(87.5e6/(32*10e3)),
                "full_nodes":math.ceil(math.ceil(1000/32)/8)+1,
                "sparse_nodes":math.ceil(math.ceil(1000/(32*.6))/8)+1,
                "peak_TB":1000*30000*30*86400/1e12, "average_TB":200*30000*30*86400/1e12}
    tokens={"rooms_cpu":"rooms_cpu=floor(2400/180)=13","rooms_ram":"rooms_ram=16",
            "rooms_down":"rooms_down=91","rooms_up":"rooms_up=273",
            "full_nodes":"32rooms→5nodes","sparse_nodes":"53rooms→8nodes",
            "peak_TB":"77.76TB","average_TB":"15.552TB"}
    expected_values=dict(zip(tokens,[13,16,91,273,5,8,77.76,15.552]))
    for k,v in calculated.items():check(math.isclose(v,expected_values[k]) and tokens[k] in g,"sizing example "+k)
    return {"kind":"STATIC_PLAN_CHECK_NOT_RUNTIME","revision":revision,
            "result":"PASS_STATIC_ONLY" if not errors else "FAIL",
            "timestamp":datetime.datetime.now().astimezone().isoformat(),"manifest_sha256":aggregate,
            "plans":stats,"dependencies":graph,"topological_order":order,"sizing_illustration":calculated,
            "errors":errors,"warnings":warnings,
            "limits":"Checks structure, declared graph and examples; semantic completeness requires independent review; runtime/human/scale/legal not tested."}

def freeze(revision):
    rows=[]
    for n in NAMES:
        raw=(Z/n).read_bytes()
        rows.append({"path":n,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)})
    aggregate=hashlib.sha256("\n".join(sorted(f"{r['path']} {r['sha256']}" for r in rows)).encode()).hexdigest()
    return {"revision":revision,"proof_class":"PLAN_DESIGN","files":rows,"manifest_sha256":aggregate,
            "frozen_at":datetime.datetime.now().astimezone().isoformat()}

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p=argparse.ArgumentParser();p.add_argument("--manifest",default="freeze-s18.json")
    p.add_argument("--output",default="static-s18.json");p.add_argument("--freeze",action="store_true")
    p.add_argument("--inputs-dir",default=None,help="alternate directory holding *.snapshot copies for negative checks")
    p.add_argument("--revision",default="S18");a=p.parse_args()
    if a.freeze:
        (OUT/a.manifest).write_text(json.dumps(freeze(a.revision),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest=json.loads((OUT/a.manifest).read_text(encoding="utf-8"))
    if a.inputs_dir:
        inputs={n:(Path(a.inputs_dir)/(n+".snapshot")).read_bytes() for n in NAMES}
    else:
        inputs={n:(Z/n).read_bytes() for n in NAMES}
    result=validate(manifest,inputs,Z)
    (OUT/a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("dependencies","topological_order")},ensure_ascii=False,indent=2))
    return 0 if result["result"]=="PASS_STATIC_ONLY" else 1
if __name__=="__main__":sys.exit(main())
