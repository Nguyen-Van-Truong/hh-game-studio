"""Validate plan structure and declared dependencies, never runtime readiness."""
from pathlib import Path
from collections import Counter
import argparse, datetime, hashlib, json, math, re, sys

OUT = Path(__file__).resolve().parent
Z = OUT.parents[1]
NAMES = ["8-9-godot-blender-agent-studio-plan.txt", "8-9-hh-world-gameplay-viet-nam-plan.txt"]
EXPECTED = [[f"GT-{i:02}" for i in range(1,11)],
            [f"H2-P{p}-{i:02}" for p,n in enumerate([3,3,4,4,4,3,3,3,3,2]) for i in range(1,n+1)]]

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
    for index, name in enumerate(NAMES):
        raw = inputs[name]
        try: s = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            errors.append(name+": invalid UTF-8"); continue
        sha = hashlib.sha256(raw).hexdigest()
        check(by_name.get(name,{}).get("sha256")==sha, name+": source hash")
        check(by_name.get(name,{}).get("bytes")==len(raw), name+": byte count")
        check(not any(c in s for c in ["\r","\x00","\ufffd","\ufeff"]), name+": LF/control/BOM")
        check(not re.search(r"(?m)^(?:<{7}|={7}|>{7}|\+)",s), name+": conflict/patch residue")
        for key,value in {"PLAN_REVISION":revision, "EXECUTION_AUTHORIZATION":"PLAN_ONLY",
                          "IMPLEMENTATION":"NOT_STARTED", "RUNTIME_ACCEPTANCE":"NONE",
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
        check(all(m.group(5)=="PLANNED" for m in table), name+": table status")
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
        prefix,count=[("TX",18),("EX",44)][index]
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
    # Recompute concrete illustrative arithmetic; no deployment capacity proof.
    g=inputs[NAMES[1]].decode("utf-8")
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
            "limits":"Checks structure, declared graph and examples; semantic completeness requires independent review; runtime/human/scale not tested."}

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    p=argparse.ArgumentParser();p.add_argument("--manifest",default="freeze-s5.json")
    p.add_argument("--output",default="static-s5.json");a=p.parse_args()
    manifest=json.loads((OUT/a.manifest).read_text(encoding="utf-8"))
    inputs={n:(Z/n).read_bytes() for n in NAMES}
    result=validate(manifest,inputs,Z)
    (OUT/a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("dependencies","topological_order")},ensure_ascii=False,indent=2))
    return 0 if result["result"]=="PASS_STATIC_ONLY" else 1
if __name__=="__main__":sys.exit(main())

